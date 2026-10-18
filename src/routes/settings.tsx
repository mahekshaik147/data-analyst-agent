import { createFileRoute } from "@tanstack/react-router";
import { SettingsPage } from "@/components/analytics/workspace";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings · Data Analyst Agent" },
      {
        name: "description",
        content: "Configure the analytics API connection and workspace display preferences.",
      },
      { property: "og:title", content: "Settings · Data Analyst Agent" },
      {
        property: "og:description",
        content: "Configure the analytics API connection and workspace display preferences.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: SettingsPage,
});
