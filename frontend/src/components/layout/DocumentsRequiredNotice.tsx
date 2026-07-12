import { Link } from "react-router-dom";
import { FileStack } from "lucide-react";
import { Button } from "@/components/ui/button";

export function DocumentsRequiredNotice({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-rule px-6 py-16 text-center">
      <FileStack className="text-ink-faint" size={28} />
      <p className="max-w-sm text-sm text-ink-soft">{message}</p>
      <Link to="/">
        <Button variant="brass" size="sm">
          Go to Documents
        </Button>
      </Link>
    </div>
  );
}
