import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { UploadCloud, CheckCircle2, FileText, Loader2 } from "lucide-react";
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
    if (!ACCEPTED_EXTENSIONS.includes(ext)) return;
    setFile(selected);
  };

  const onSubmit = (values: FormValues) => mutation.mutate(values);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Document {label}</CardTitle>
        {current && (
          <span className="flex items-center gap-1.5 text-xs font-medium text-match">
            <CheckCircle2 size={14} /> Ingested
          </span>
        )}
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div
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
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed py-8 text-center transition-colors",
              isDragging ? "border-brass bg-brass-soft" : "border-rule hover:border-ink-faint",
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_EXTENSIONS.join(",")}
              className="hidden"
              onChange={(e) => onFileSelected(e.target.files?.[0] ?? null)}
            />
            {file ? (
              <>
                <FileText className="text-brass" size={22} />
                <span className="text-sm font-medium text-ink">{file.name}</span>
              </>
            ) : (
              <>
                <UploadCloud className="text-ink-faint" size={22} />
                <span className="text-sm text-ink-soft">Drop a .pdf or .docx, or click to browse</span>
              </>
            )}
          </div>

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
            <p className="text-xs text-missing">
              {mutation.error instanceof ApiError ? mutation.error.message : "Ingestion failed."}
            </p>
          )}

          <Button type="submit" variant="brass" className="w-full" disabled={!file || mutation.isPending}>
            {mutation.isPending && <Loader2 size={14} className="animate-spin" />}
            {current ? "Re-ingest" : "Ingest document"}
          </Button>

          {current && (
            <dl className="grid grid-cols-3 gap-2 border-t border-rule pt-3 font-mono text-[11px] text-ink-soft">
              <div>
                <dt className="text-ink-faint">chunks</dt>
                <dd className="text-ink">{current.chunks_created}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">parent</dt>
                <dd className="text-ink">{current.parent_chunks}</dd>
              </div>
              <div>
                <dt className="text-ink-faint">child</dt>
                <dd className="text-ink">{current.child_chunks}</dd>
              </div>
            </dl>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
