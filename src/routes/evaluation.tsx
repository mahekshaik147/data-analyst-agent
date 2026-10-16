import { createFileRoute } from "@tanstack/react-router";
import { EvaluationPage } from "@/components/analytics/workspace";

export const Route = createFileRoute("/evaluation")({
  head: () => ({ meta: [
    { title: "Evaluation Center · Data Analyst Agent" },
    { name: "description", content: "Review real text-to-SQL benchmark results and run evaluations against your backend." },
    { property: "og:title", content: "Evaluation Center · Data Analyst Agent" },
    { property: "og:description", content: "Review real text-to-SQL benchmark results and run evaluations against your backend." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: EvaluationPage,
});