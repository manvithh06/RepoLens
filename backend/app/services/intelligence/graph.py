"""Turn import edges into a file graph, import cycles and a folder-level architecture."""

from collections import Counter, deque
from posixpath import dirname

from app.core.limits import (
    MAX_ARCHITECTURE_DEPTH,
    MAX_ARCHITECTURE_GROUPS,
    MAX_CYCLES,
    MAX_EXTERNAL_PACKAGES,
    MAX_GRAPH_NODES,
)
from app.schemas.analysis import (
    ArchitectureEdge,
    ArchitectureGraph,
    ArchitectureModule,
    Cycle,
    ExternalPackage,
    GraphEdge,
    GraphNode,
    ImportGraph,
    ModuleKind,
)
from app.services.intelligence.imports import ImportResult
from app.services.intelligence.languages import language_of
from app.services.intelligence.paths import folder_kind
from app.services.intelligence.reader import RepoReader

ROOT_GROUP = "(root)"
OTHER_GROUP = "(other folders)"


Adjacency = dict[str, list[str]]


def _adjacency(imports: ImportResult) -> Adjacency:
    return {source: sorted(targets) for source, targets in imports.edges.items()}


# ---------- cycles ----------


def strongly_connected(nodes: list[str], adjacency: Adjacency) -> list[list[str]]:
    """Tarjan's algorithm without recursion, so deep graphs cannot overflow the stack."""
    index_of: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0

    for start in nodes:
        if start in index_of:
            continue
        work: list[tuple[str, int]] = [(start, 0)]
        while work:
            node, child_index = work[-1]
            if child_index == 0:
                index_of[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            children = adjacency.get(node, [])
            if child_index < len(children):
                work[-1] = (node, child_index + 1)
                child = children[child_index]
                if child not in index_of:
                    work.append((child, 0))
                elif child in on_stack:
                    low[node] = min(low[node], index_of[child])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index_of[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)
    return components


def _shortest_loop(start: str, members: set[str], adjacency: Adjacency) -> list[str]:
    """Breadth-first search from `start` back to itself, staying inside the group."""
    previous: dict[str, str] = {}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for child in adjacency.get(node, []):
            if child not in members:
                continue
            if child == start:
                loop = [node]
                while loop[-1] != start:
                    loop.append(previous[loop[-1]])
                return list(reversed(loop))
            if child not in previous:
                previous[child] = node
                queue.append(child)
    return sorted(members)


def find_cycles(nodes: list[str], adjacency: Adjacency) -> list[Cycle]:
    groups = [c for c in strongly_connected(nodes, adjacency) if len(c) > 1]
    groups.sort(key=lambda c: (-len(c), min(c)))
    return [
        Cycle(
            files=_shortest_loop(min(group), set(group), adjacency),
            group_size=len(group),
        )
        for group in groups[:MAX_CYCLES]
    ]


# ---------- file graph ----------


def build_import_graph(reader: RepoReader, imports: ImportResult) -> ImportGraph:
    adjacency = _adjacency(imports)
    in_degree: Counter[str] = Counter()
    for targets in adjacency.values():
        in_degree.update(targets)

    def degree(path: str) -> int:
        return len(adjacency.get(path, [])) + in_degree[path]

    files = imports.script_files
    ranked = sorted(files, key=lambda p: (-degree(p), p))
    kept = set(ranked[:MAX_GRAPH_NODES])
    total_edges = sum(len(targets) for targets in adjacency.values())

    nodes = [
        GraphNode(
            id=path,
            language=language_of(path),
            size=reader.size(path),
            imports=len(adjacency.get(path, [])),
            imported_by=in_degree[path],
        )
        for path in sorted(kept)
    ]
    edges = [
        GraphEdge(source=source, target=target)
        for source in sorted(adjacency)
        if source in kept
        for target in adjacency[source]
        if target in kept
    ]
    externals = sorted(imports.external.items(), key=lambda item: (-item[1], item[0]))
    return ImportGraph(
        nodes=nodes,
        edges=edges,
        truncated=len(files) > len(kept),
        total_files=len(files),
        total_edges=total_edges,
        cycles=find_cycles(files, adjacency),
        external_packages=[
            ExternalPackage(name=name, ecosystem=ecosystem, files=count)  # type: ignore[arg-type]
            for (name, ecosystem), count in externals[:MAX_EXTERNAL_PACKAGES]
        ],
        parse_errors=imports.parse_errors,
        unresolved_imports=imports.unresolved,
    )


# ---------- architecture ----------


def _group_at(path: str, depth: int) -> str:
    folder = dirname(path)
    if not folder:
        return ROOT_GROUP
    return "/".join(folder.split("/")[:depth])


def module_kind(group: str) -> ModuleKind:
    return folder_kind(group)


def _choose_depth(files: list[str]) -> int:
    best = 1
    for depth in range(1, MAX_ARCHITECTURE_DEPTH + 1):
        if len({_group_at(p, depth) for p in files}) <= MAX_ARCHITECTURE_GROUPS:
            best = depth
    return best


def build_architecture(reader: RepoReader, imports: ImportResult) -> ArchitectureGraph:
    files = imports.script_files
    if not files:
        return ArchitectureGraph(depth=0, modules=[], edges=[])

    depth = _choose_depth(files)
    group_of = {path: _group_at(path, depth) for path in files}

    counts = Counter(group_of.values())
    if len(counts) > MAX_ARCHITECTURE_GROUPS:
        # Even the top level is too wide: keep the biggest folders, fold the rest.
        keep = {g for g, _ in counts.most_common(MAX_ARCHITECTURE_GROUPS - 1)}
        group_of = {p: g if g in keep else OTHER_GROUP for p, g in group_of.items()}

    sizes: Counter[str] = Counter()
    file_counts: Counter[str] = Counter()
    for path, group in group_of.items():
        sizes[group] += reader.size(path)
        file_counts[group] += 1

    weights: Counter[tuple[str, str]] = Counter()
    for source, targets in imports.edges.items():
        for target in targets:
            a, b = group_of.get(source), group_of.get(target)
            if a and b and a != b:
                weights[(a, b)] += 1

    modules = [
        ArchitectureModule(
            id=group,
            label=group,
            kind="source" if group in (ROOT_GROUP, OTHER_GROUP) else module_kind(group),
            file_count=file_counts[group],
            size=sizes[group],
        )
        for group in sorted(file_counts)
    ]
    edges = [
        ArchitectureEdge(source=a, target=b, weight=weight)
        for (a, b), weight in sorted(weights.items())
    ]
    return ArchitectureGraph(depth=depth, modules=modules, edges=edges)
