import { createFileRoute } from "@tanstack/react-router";
import { DatasetPage } from "@/components/analytics/workspace";

export const Route = createFileRoute("/datasets")({
  head: () => ({
    meta: [
      { title: "Dataset Explorer · Data Analyst Agent" },
      {
        name: "description",
        content: "Inspect live database tables, columns, relationships, and sample records.",
      },
      { property: "og:title", content: "Dataset Explorer · Data Analyst Agent" },
      {
        property: "og:description",
        content: "Inspect live database tables, columns, relationships, and sample records.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DatasetPage,
});
