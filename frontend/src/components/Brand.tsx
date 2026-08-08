interface BrandProps {
  compact?: boolean;
  inverse?: boolean;
}

export function Brand({ compact = false, inverse = false }: BrandProps) {
  return (
    <div className={`brand ${inverse ? "brand--inverse" : ""}`} aria-label="Memora">
      <span className="brand__mark" aria-hidden="true">M</span>
      {!compact && (
        <span className="brand__words">
          <strong>Memora</strong>
          <small>Gestión que acompaña</small>
        </span>
      )}
    </div>
  );
}

