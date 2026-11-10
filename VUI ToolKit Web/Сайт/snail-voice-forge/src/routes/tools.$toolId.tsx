import { createFileRoute, notFound } from "@tanstack/react-router";
import { ToolPage } from "@/components/tool-page";
import { getTool, tools, type ToolId } from "@/lib/tools";

export const Route = createFileRoute("/tools/$toolId")({
  beforeLoad: ({ params }) => { if (!getTool(params.toolId)) throw notFound(); },
  head: ({ params }) => { const tool = getTool(params.toolId); const title = `${tool?.title || "Инструмент"} — VUI ToolKit`; const description = tool?.description || "Аудиоинструмент VUI ToolKit"; return { meta: [{ title }, { name: "description", content: description }, { property: "og:title", content: title }, { property: "og:description", content: description }, { property: "og:type", content: "website" }, { name: "twitter:card", content: "summary_large_image" }] }; },
  component: ToolRoute,
});

function ToolRoute() { const { toolId } = Route.useParams(); const id = tools.some((tool) => tool.id === toolId) ? toolId as ToolId : "process"; return <ToolPage toolId={id} />; }