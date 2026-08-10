import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
  page: number;
  totalPages: number;
  hasNext: boolean;
  hasPrevious: boolean;
  onChange: (page: number) => void;
}

export function Pagination({ page, totalPages, hasNext, hasPrevious, onChange }: PaginationProps) {
  return (
    <footer className="pagination">
      <span>Página {page} de {Math.max(totalPages, 1)}</span>
      <div>
        <button type="button" disabled={!hasPrevious} onClick={() => onChange(page - 1)}>
          <ChevronLeft size={16} /> Anterior
        </button>
        <button type="button" disabled={!hasNext} onClick={() => onChange(page + 1)}>
          Siguiente <ChevronRight size={16} />
        </button>
      </div>
    </footer>
  );
}
