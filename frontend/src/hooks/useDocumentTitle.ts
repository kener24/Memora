import { useEffect } from "react";

export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · Memora`;
    return () => {
      document.title = "Memora";
    };
  }, [title]);
}

