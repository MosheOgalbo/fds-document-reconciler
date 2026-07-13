import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, WifiOff } from "lucide-react";
import { checkHealth } from "@/lib/api";

export function ConfigurationBanner() {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    retry: false,
    refetchInterval: 30_000,
  });

  if (isError) {
    return (
      <div className="flex items-center gap-2 border-b border-missing/30 bg-missing-soft px-6 py-2.5 text-sm text-missing">
        <WifiOff size={15} className="shrink-0" />
        <span>
          Can't reach the backend at <code className="font-mono">http://localhost:8000</code>. Run{" "}
          <code className="font-mono">docker compose up --build</code> from the project root.
        </span>
      </div>
    );
  }

  if (!data) return null;

  if (!data.gemini_configured && !data.openai_configured) {
    return (
      <div className="flex items-center gap-2 border-b border-diff/30 bg-diff-soft px-6 py-2.5 text-sm text-diff">
        <AlertTriangle size={15} className="shrink-0" />
        <span>
          Backend is running but <strong>GEMINI_API_KEY</strong> is missing. Get a free key at{" "}
          <a href="https://aistudio.google.com/apikey" className="underline" target="_blank" rel="noreferrer">
            Google AI Studio
          </a>
          , add it to <code className="font-mono">backend/.env</code>, and restart Docker.
        </span>
      </div>
    );
  }

  return null;
}
