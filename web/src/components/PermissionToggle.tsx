import React from 'react';
import { PolicyValue } from '../types';
import { Check, X, Minus } from 'lucide-react';

interface PermissionToggleProps {
  label: string;
  description?: string;
  value: PolicyValue;
  onChange: (newValue: PolicyValue) => void;
  disabled?: boolean;
}

export const PermissionToggle: React.FC<PermissionToggleProps> = ({
  label,
  description,
  value,
  onChange,
  disabled = false,
}) => {
  return (
    <div className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-gray-800/40 transition-colors">
      <div className="pr-4 flex-1">
        <span className="text-sm font-medium text-gray-200 block">{label}</span>
        {description && <span className="text-xs text-gray-400 block mt-0.5">{description}</span>}
      </div>

      <div className="flex items-center bg-[#0B0E14] border border-gray-800 rounded-lg p-0.5 shrink-0">
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange('allow')}
          className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition-all ${
            value === 'allow'
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow'
              : 'text-gray-400 hover:text-white'
          }`}
          title="Allow"
        >
          <Check className="w-3.5 h-3.5" />
          <span>ALLOW</span>
        </button>

        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange('deny')}
          className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition-all ${
            value === 'deny'
              ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30 shadow'
              : 'text-gray-400 hover:text-white'
          }`}
          title="Deny"
        >
          <X className="w-3.5 h-3.5" />
          <span>DENY</span>
        </button>

        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange('inherit')}
          className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold transition-all ${
            value === 'inherit'
              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30 shadow'
              : 'text-gray-400 hover:text-white'
          }`}
          title="Inherit"
        >
          <Minus className="w-3.5 h-3.5" />
          <span>INHERIT</span>
        </button>
      </div>
    </div>
  );
};
