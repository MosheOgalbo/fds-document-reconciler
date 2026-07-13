import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { UploadCloud, CheckCircle2, FileText, Loader2, FolderOpen, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ingestDocument, ApiError } from "@/lib/api";
import { useDocuments } from "@/lib/documentsContext";
import { cn } from "@/lib/utils";

const schema = z.object({
  document_name: z.string().min(1, "Required"),
  version: z.string().min(1, "Required"),
});
type FormValues = z.infer<typeof schema>;

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".dotx"];

export function DocumentUploadCard({
  label,
  defaultName,
  defaultVersion,
}: {
  label: "A" | "B";
  defaultName: string;
  defaultVersion: string;
}) {
  const { docA, docB, setDocument } = useDocuments();
  const current = label === "A" ? docA : docB;
  const [file, setFile] = React.useState<File | null>(null);
  const [fileError, setFileError] = React.useState<string | null>(null);
  const [isDragging, setIsDragging] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { document_name: defaultName, version: defaultVersion },
  });

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      if (!file) throw new Error("Choose a file first");
      return ingestDocument(file, values.document_name, values.version);
    },
    onSuccess: (result, values) => {
      setDocument(label, { ...result, label, fileName: file!.name });
    },
  });

  const onFileSelected = (selected: File | null) => {
    if (!selected) return;
    const ext = selected.name.slice(selected.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setFileError(`Unsupported file type. Use ${ACCEPTED_EXTENSIONS.join(", ")}.`);
      return;
    }
    setFileError(null);
    setFile(selected);
  };

  const onBrowseClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    fileInputRef.current?.click();
  };

  const onSubmit = (values: FormValues) => mutation.mutate(values);

  const isReady = Boolean(current);

  return (
    <Card className={cn("transition-shadow", isReady && "border-match/40 shadow-card ring-1 ring-match/20")}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-md text-xs font-bold",
              isReady ? "bg-match text-white" : "bg-brass-soft text-brass-dark",
            )}
          >
            {label}
          </span>
          <CardTitle className="text-base">Document {label}</CardTitle>
        </div>
        {isReady && (
          <span className="flex items-center gap-1.5 text-xs font-medium text-match">
            <CheckCircle2 size={14} /> Ready
          </span>
        )}
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              onFileSelected(e.dataTransfer.files?.[0] ?? null);
            }}
            className={cn(
              "flex min-h-[180px] cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors",
              isDragging && "border-brass bg-brass-soft",
              isReady && !isDragging && "border-match/30 bg-match-soft/30",
              !isReady && !isDragging && "border-rule hover:border-brass/50 hover:bg-paper",
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS.join(",")}
              className="hidden"
              onChange={(e) => onFileSelected(e.target.files?.[0] ?? null)}
            />
            {file || current ? (
              <>
                <FileText className={cn(isReady ? "text-match" : "text-brass")} size={28} />
                <span className="max-w-full truncate text-sm font-medium text-ink">
                  {file?.name ?? current?.fileName}
                </span>
                <span className="text-xs text-ink-soft">
                  {file
                    ? `${(file.size / 1024).toFixed(0)} KB · click or drop to replace`
                    : `${current?.document_name} · ${current?.version} · ingested`}
                </span>
                {file && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                  >
                    <X size={14} /> Clear selection
                  </Button>
                )}
              </>
            ) : (
              <>
                <UploadCloud className="text-ink-faint" size={28} />
                <span className="text-sm font-medium text-ink">Click or drag & drop</span>
                <span className="text-xs text-ink-soft">PDF or DOCX from your computer</span>
              </>
            )}
            <Button type="button" variant="outline" size="sm" onClick={onBrowseClick}>
              <FolderOpen size={14} />
              Browse files
            </Button>
          </div>

          {fileError && <p className="text-xs text-missing">{fileError}</p>}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-soft">Document name</label>
              <Input {...register("document_name")} />
              {errors.document_name && (
                <p className="mt-1 text-xs text-missing">{errors.document_name.message}</p>
              )}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-soft">Version label</label>
              <Input {...register("version")} />
              {errors.version && <p className="mt-1 text-xs text-missing">{errors.version.message}</p>}
            </div>
          </div>

          {mutation.isError && (
            <p className="rounded-md bg-missing-soft px-3 py-2 text-xs text-missing">
              {mutation.error instanceof ApiError ? mutation.error.message : "Ingestion failed."}
            </p>
          )}

          <Button type="submit" variant="brass" className="w-full" disabled={!file || mutation.isPending}>
            {mutation.isPending && <Loader2 size={14} className="animate-spin" />}
            {mutation.isPending ? "Ingesting…" : isReady ? "Re-ingest document" : "Ingest document"}
          </Button>

          {current && (
            <dl className="grid grid-cols-3 gap-2 rounded-md bg-paper px-3 py-3 font-mono text-[11px] text-ink-soft">
              <div>
                <dt className="text-ink-faint">chunks</dt>
                <dd className="text-base font-semibold text-ink">{current.chunks_created}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">parent</dt>
                <dd className="text-base font-semibold text-ink">{current.parent_chunks}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">child</dt>
                <dd className="text-base font-semibold text-ink">{current.child_chunks}</dd>
              </div>
            </dl>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
