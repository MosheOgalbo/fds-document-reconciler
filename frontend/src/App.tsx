import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { DocumentsProvider } from "@/lib/documentsContext";
import { AppShell } from "@/components/layout/AppShell";
import { IngestPage } from "@/pages/IngestPage";
import { ComparePage } from "@/pages/ComparePage";
import { ChatPage } from "@/pages/ChatPage";
import { SummaryPage } from "@/pages/SummaryPage";

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <DocumentsProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<IngestPage />} />
              <Route path="compare" element={<ComparePage />} />
              <Route path="chat" element={<ChatPage />} />
              <Route path="summary" element={<SummaryPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </DocumentsProvider>
    </QueryClientProvider>
  );
}
