import { useQuery } from "@tanstack/react-query";
import { getLatestNews } from "../../services/apiClient";
import type { NewsResponse } from "../../types";

export function useLatestNews(limit = 5) {
  return useQuery<NewsResponse, Error>({
    queryKey: ["news", "latest", limit],
    queryFn: () => getLatestNews(limit),
    staleTime: 5 * 60 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}