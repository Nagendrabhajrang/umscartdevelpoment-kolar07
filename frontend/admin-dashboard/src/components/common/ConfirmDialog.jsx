import { AlertTriangle } from "lucide-react";
import Modal from "./Modal";
import Button from "./Button";

export default function ConfirmDialog({ open, onClose, onConfirm, title = "Confirm action", description, confirmLabel = "Confirm", tone = "danger", loading = false }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button variant={tone} size="sm" onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
        </div>
      }
    >
      <div className="flex gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-amber-100 text-amber-700">
          <AlertTriangle className="h-4.5 w-4.5" aria-hidden="true" />
        </span>
        <p className="text-sm text-slate-600">{description}</p>
      </div>
    </Modal>
  );
}
