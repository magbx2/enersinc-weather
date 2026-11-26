import { useEffect, useId, useMemo, useState } from "react";
import { Alert, AutoComplete, Spin } from "antd";

import { api } from "../api/client";
import type { CityCandidate } from "../types/weather";

function fold(value: string): string {
  return value.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

function labelFor(candidate: CityCandidate): string {
  const region = candidate.state ? `, ${candidate.state}` : "";
  return `${candidate.name}${region} (${candidate.country_code})`;
}

export interface CitySelectorProps {
  label: string;
  value: string;
  otherValue?: string;
  onSelect: (city: string) => void;
  disabled?: boolean;
}

export function CitySelector({ label, value, otherValue, onSelect, disabled }: CitySelectorProps) {
  const id = useId();
  const [inputValue, setInputValue] = useState(value);
  const [options, setOptions] = useState<{ value: string; label: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setInputValue(value);
  }, [value]);

  useEffect(() => {
    const query = inputValue.trim();
    if (query.length === 0 || query === value) {
      setOptions([]);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      setError(null);
      api
        .searchCities(query, 5, controller.signal)
        .then((results) => {
          setOptions(
            results.map((candidate) => ({ value: candidate.name, label: labelFor(candidate) })),
          );
          if (results.length === 0) {
            setError(`Ninguna ciudad coincide con “${query}”.`);
          }
        })
        .catch((cause: unknown) => {
          if (cause instanceof DOMException && cause.name === "AbortError") return;
          setOptions([]);
          setError(cause instanceof Error ? cause.message : "La búsqueda de ciudades falló.");
        })
        .finally(() => setLoading(false));
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [inputValue, value]);

  const handleSelect = (selected: string) => {
    if (otherValue && fold(selected) === fold(otherValue)) {
      setError("Las dos ciudades deben ser diferentes.");
      setInputValue(value);
      return;
    }
    setError(null);
    setOptions([]);
    setInputValue(selected);
    onSelect(selected);
  };

  const suffix = useMemo(() => (loading ? <Spin size="small" /> : null), [loading]);

  return (
    <div>
      <label htmlFor={id} style={{ display: "block", marginBottom: 4, fontWeight: 500 }}>
        {label}
      </label>
      <AutoComplete
        id={id}
        aria-label={label}
        value={inputValue}
        options={options}
        style={{ width: "100%" }}
        disabled={disabled}
        onSearch={(text) => {
          setInputValue(text);
          setError(null);
        }}
        onSelect={handleSelect}
      />
      {suffix}
      {error ? (
        <Alert type="warning" showIcon style={{ marginTop: 8 }} message={error} role="alert" />
      ) : null}
    </div>
  );
}
