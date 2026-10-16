import { createFileRoute } from "@tanstack/react-router";
import { AnalystPage, WorkspaceLayout } from "@/components/analytics/workspace";

export const Route = createFileRoute("/analyst")({
  validateSearch: (search: Record<string, unknown>) => ({ question: typeof search["question"] === "string" ? search["question"] : undefined }),
  head: () => ({ meta: [
    { title: "AI Analyst · Data Analyst Agent" },
    { name: "description", content: "Ask questions about your business data and inspect the SQL and results returned by your analytics service." },
    { property: "og:title", content: "AI Analyst · Data Analyst Agent" },
    { property: "og:description", content: "Ask questions about your business data and inspect the SQL and results returned by your analytics service." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: () => <WorkspaceLayout><AnalystPage /></WorkspaceLayout>,
});