import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, WifiOff } from "lucide-react";
import { checkHealth } from "@/lib/api";

export function ConfigurationBanner() {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    retry: false,
    refetchInterval: 30_000, // keep checking — a common flow is: start app, add keys, restart backend
  });

  if (isError) {
    return (
      <div className="flex items-center gap-2 border-b border-missing/30 bg-missing-soft px-6 py-2.5 text-sm text-missing">
        <WifiOff size={15} className="shrink-0" />
        <span>
          Can't reach the backend at <code className="font-mono">VITE_API_BASE_URL</code>. Is it
          running? See <code className="font-mono">backend/README</code> — <code>uvicorn app.main:app --reload --port 8000</code>.
        </span>
      </div>
    );
  }

  if (!data) return null;

  const missing: string[] = [];
  if (!data.openai_configured) missing.push("OPENAI_API_KEY");
  if (!data.pinecone_configured) missing.push("PINECONE_API_KEY");

  if (missing.length === 0) return null;

  return (
    <div className="flex items-center gap-2 border-b border-diff/30 bg-diff-soft px-6 py-2.5 text-sm text-diff">
      <AlertTriangle size={15} className="shrink-0" />
      <span>
        Backend is running but not fully configured — <strong>{missing.join(" and ")}</strong>{" "}
        {missing.length > 1 ? "are" : "is"} missing. Add{" "}
        {missing.length > 1 ? "them" : "it"} to <code className="font-mono">backend/.env</code>{" "}
        (copy from <code className="font-mono">backend/.env.example</code>) and restart the backend.
        Ingestion and queries will fail until this is set.
      </span>
    </div>
  );
}
