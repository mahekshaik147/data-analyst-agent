import { createFileRoute } from "@tanstack/react-router";
import { OverviewPage } from "@/components/analytics/workspace";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Overview · Data Analyst Agent" },
      { name: "description", content: "Explore your connected business data with natural-language analytics and transparent SQL." },
      { property: "og:title", content: "Overview · Data Analyst Agent" },
      { property: "og:description", content: "Explore your connected business data with natural-language analytics and transparent SQL." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: OverviewPage,
});