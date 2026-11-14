import { createContext, useContext } from 'react'

export interface RepoLinks {
  htmlUrl: string
  branch: string
}

export const RepoLinksContext = createContext<RepoLinks | null>(null)

export function useRepoLinks(): RepoLinks | null {
  return useContext(RepoLinksContext)
}
