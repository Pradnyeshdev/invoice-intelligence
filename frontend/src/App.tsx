import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode, RefObject } from 'react'
import {
  deleteInvoice,
  fetchInvoice,
  fetchInvoices,
  processInvoice,
  uploadInvoice,
} from './api'
import type { InvoiceRecord, InvoiceUploadResponse, ValidationCheck } from './types'

type IconName = 'grid' | 'file' | 'upload' | 'refresh' | 'arrow' | 'check' | 'alert' | 'clock' | 'trash' | 'close' | 'receipt' | 'chevron'

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const }
  const paths: Record<IconName, ReactNode> = {
    grid: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></>,
    file: <><path d="M13.5 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9z" /><path d="M13 3.5V9h6M8.5 13h7M8.5 16.5h7" /></>,
    upload: <><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" /><path d="M5 14.5v4A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5v-4" /></>,
    refresh: <><path d="M20 7v5h-5" /><path d="M19 12a7 7 0 0 0-12-4L5 10M4 17v-5h5" /><path d="M5 12a7 7 0 0 0 12 4l2-2" /></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    check: <path d="m5 12.5 4.2 4.2L19 7" />,
    alert: <><path d="M12 3.5 2.9 19.2a1.5 1.5 0 0 0 1.3 2.3h15.6a1.5 1.5 0 0 0 1.3-2.3z" /><path d="M12 9v4.5m0 3h.01" /></>,
    clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2" /></>,
    trash: <><path d="M4.5 7h15M9 7V4.5h6V7m2.5 0-.8 13h-9L7 7m3.5 3v6m3-6v6" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    receipt: <><path d="M5 3.5 7 5l2-1.5L11 5l2-1.5L15 5l2-1.5 2 1.5v16l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5L7 21l-2-1.5z" /><path d="M8.5 9h7m-7 4h7m-7 4h4" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
  }
  return <svg {...common}>{paths[name]}</svg>
}

function formatAmount(amount: string | null, currency: string | null) {
  if (amount === null) return '—'
  const numericAmount = Number(amount)
  if (!Number.isFinite(numericAmount)) return amount
  if (currency) {
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 2 }).format(numericAmount)
    } catch {
      return `${currency} ${numericAmount.toFixed(2)}`
    }
  }
  return numericAmount.toFixed(2)
}

function formatDate(value: string | null) {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

function formatCreatedAt(value: string) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

function StatusBadge({ valid }: { valid: boolean }) {
  return <span className={`status-badge ${valid ? 'is-valid' : 'is-invalid'}`}><span className="status-dot" />{valid ? 'Valid' : 'Needs review'}</span>
}

function ValidationMark({ status }: { status: ValidationCheck['status'] }) {
  if (status === 'passed') return <span className="check-mark passed"><Icon name="check" size={14} /></span>
  if (status === 'failed') return <span className="check-mark failed"><Icon name="close" size={14} /></span>
  if (status === 'warning') return <span className="check-mark warning"><Icon name="alert" size={14} /></span>
  return <span className="check-mark skipped"><Icon name="clock" size={14} /></span>
}

function InvoiceDetail({ invoice, onClose, onDelete, deleting }: { invoice: InvoiceRecord; onClose: () => void; onDelete: (invoice: InvoiceRecord) => void; deleting: boolean }) {
  return <div className="overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <aside className="detail-panel" role="dialog" aria-modal="true" aria-labelledby="detail-title">
      <div className="detail-header">
        <div>
          <p className="eyebrow">Invoice record · #{invoice.id}</p>
          <h2 id="detail-title">{invoice.invoice_number || invoice.original_filename}</h2>
          <p className="detail-vendor">{invoice.vendor_name || 'Vendor not identified'}</p>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close invoice details"><Icon name="close" /></button>
      </div>
      <div className="detail-scroll">
        <div className="detail-status-row"><StatusBadge valid={invoice.is_valid} /><span className="muted">Processed {formatCreatedAt(invoice.created_at)}</span></div>
        <section className="detail-section">
      <div className="section-heading"><h3>Extracted fields</h3><span>From uploaded document</span></div>
          <div className="field-grid">
            <Field label="Invoice number" value={invoice.invoice_number} />
            <Field label="Invoice date" value={formatDate(invoice.invoice_date)} />
            <Field label="Vendor" value={invoice.vendor_name} />
            <Field label="Currency" value={invoice.currency} />
            <Field label="Subtotal" value={formatAmount(invoice.subtotal, invoice.currency)} />
            <Field label="Tax" value={formatAmount(invoice.tax, invoice.currency)} />
            <Field label="Total" value={formatAmount(invoice.total, invoice.currency)} strong />
            <Field label="Source file" value={invoice.original_filename} />
          </div>
        </section>
        {invoice.errors.length > 0 && <section className="detail-section"><div className="section-heading"><h3>Errors</h3><span className="count-pill error-count">{invoice.errors.length}</span></div><ul className="message-list errors-list">{invoice.errors.map((message, index) => <li key={`${message}-${index}`}><Icon name="alert" size={16} />{message}</li>)}</ul></section>}
        {invoice.warnings.length > 0 && <section className="detail-section"><div className="section-heading"><h3>Warnings</h3><span className="count-pill warning-count">{invoice.warnings.length}</span></div><ul className="message-list warnings-list">{invoice.warnings.map((message, index) => <li key={`${message}-${index}`}><Icon name="alert" size={16} />{message}</li>)}</ul></section>}
        <section className="detail-section">
          <div className="section-heading"><h3>Validation checks</h3><span>{invoice.checks.length} checks</span></div>
          <div className="check-list">{invoice.checks.map((check) => <div className="check-row" key={check.name}><ValidationMark status={check.status} /><div><strong>{humanizeCheckName(check.name)}</strong><p>{check.message}</p></div></div>)}</div>
        </section>
      </div>
      <div className="detail-footer"><button className="button danger-outline" onClick={() => onDelete(invoice)} disabled={deleting}><Icon name="trash" size={16} />{deleting ? 'Deleting…' : 'Delete invoice'}</button><button className="button primary" onClick={onClose} disabled={deleting}>Done</button></div>
    </aside>
  </div>
}

function Field({ label, value, strong = false }: { label: string; value: string | null; strong?: boolean }) {
  return <div className="field-item"><span>{label}</span><strong className={strong ? 'field-total' : ''}>{value || '—'}</strong></div>
}

function humanizeCheckName(name: string) {
  return name.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function InvoiceTable({ invoices, onView, onDelete, deletingInvoiceId, compact = false }: { invoices: InvoiceRecord[]; onView: (id: number) => void; onDelete: (invoice: InvoiceRecord) => void; deletingInvoiceId: number | null; compact?: boolean }) {
  const visibleInvoices = compact ? invoices.slice(0, 5) : invoices
  return <div className="table-wrap"><table><thead><tr><th>Invoice</th><th>Vendor</th><th>Date</th><th>Total</th><th>Status</th><th>Created</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>
    {visibleInvoices.map((invoice) => <tr key={invoice.id}>
      <td><button className="invoice-link" onClick={() => onView(invoice.id)}>{invoice.invoice_number || 'Untitled invoice'}<small>{invoice.original_filename}</small></button></td>
      <td>{invoice.vendor_name || <span className="muted">Not identified</span>}</td>
      <td>{formatDate(invoice.invoice_date)}</td>
      <td className="amount-cell">{formatAmount(invoice.total, invoice.currency)}</td>
      <td><StatusBadge valid={invoice.is_valid} /></td>
      <td className="muted">{formatCreatedAt(invoice.created_at)}</td>
      <td><div className="row-actions"><button className="text-action" onClick={() => onView(invoice.id)} disabled={deletingInvoiceId === invoice.id}>View</button><button className="icon-button small" onClick={() => onDelete(invoice)} aria-label={`Delete ${invoice.invoice_number || 'invoice'}`} disabled={deletingInvoiceId === invoice.id}><Icon name="trash" size={15} /></button></div></td>
    </tr>)}
  </tbody></table></div>
}

export default function App() {
  const [activeView, setActiveView] = useState<'overview' | 'invoices'>('overview')
  const [invoices, setInvoices] = useState<InvoiceRecord[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState('')
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceRecord | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [deletingInvoiceId, setDeletingInvoiceId] = useState<number | null>(null)
  const [pendingUpload, setPendingUpload] = useState<InvoiceUploadResponse | null>(null)
  const [processingResult, setProcessingResult] = useState<InvoiceRecord | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const [actionError, setActionError] = useState('')
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const refreshHistory = useCallback(async (showLoading = true) => {
    if (showLoading) setHistoryLoading(true)
    setHistoryError('')
    try {
      setInvoices(await fetchInvoices())
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : 'Unable to load invoice history.')
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => { void refreshHistory() }, [refreshHistory])

  const validCount = useMemo(() => invoices.filter((invoice) => invoice.is_valid).length, [invoices])
  const invalidCount = invoices.length - validCount

  function chooseFile(candidate: File | undefined) {
    if (!candidate) return
    setActionMessage('')
    setActionError('')
    const extension = candidate.name.toLowerCase().split('.').pop()
    const supportedType = ['application/pdf', 'image/png', 'image/jpeg'].includes(candidate.type)
    if (!supportedType && !['pdf', 'png', 'jpg', 'jpeg'].includes(extension || '')) {
      setFile(null)
      setActionError('Choose a PDF, PNG, or JPEG file to upload.')
      return
    }
    if (candidate.size > 10 * 1024 * 1024) {
      setFile(null)
      setActionError('The selected file exceeds the 10 MB upload limit.')
      return
    }
    setFile(candidate)
  }

  async function runProcessing(upload: InvoiceUploadResponse) {
    setPendingUpload(upload)
    setProcessing(true)
    setActionError('')
    setActionMessage(`Uploaded ${upload.original_filename}. Processing invoice…`)
    try {
      const processed = await processInvoice(upload.upload_id)
      setProcessingResult(processed)
      setPendingUpload(null)
      setActionMessage(processed.is_valid ? 'Invoice processed and saved to history.' : 'Invoice processed with validation issues. Review the result below.')
      await refreshHistory(false)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Invoice processing failed.')
      setActionMessage('The file was uploaded, but processing did not complete.')
    } finally {
      setProcessing(false)
    }
  }

  async function handleUpload() {
    if (!file) {
      fileInput.current?.click()
      return
    }
    setUploading(true)
    setActionError('')
    setActionMessage('Uploading document…')
    setProcessingResult(null)
    try {
      const upload = await uploadInvoice(file)
      setFile(null)
      if (fileInput.current) fileInput.current.value = ''
      setUploading(false)
      await runProcessing(upload)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'The file could not be uploaded.')
      setActionMessage('Upload did not complete.')
    } finally {
      setUploading(false)
    }
  }

  async function retryProcessing() {
    if (pendingUpload) await runProcessing(pendingUpload)
  }

  async function openInvoice(invoiceId: number) {
    setDetailLoading(true)
    setSelectedInvoice(null)
    setActionError('')
    try {
      setSelectedInvoice(await fetchInvoice(invoiceId))
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to open invoice details.')
    } finally {
      setDetailLoading(false)
    }
  }

  async function removeInvoice(invoice: InvoiceRecord) {
    const label = invoice.invoice_number || invoice.original_filename
    if (deletingInvoiceId !== null || !window.confirm(`Delete ${label} and its uploaded file from this workspace?`)) return
    setDeletingInvoiceId(invoice.id)
    try {
      await deleteInvoice(invoice.id)
      setSelectedInvoice(null)
      setProcessingResult((current) => current?.id === invoice.id ? null : current)
      setActionError('')
      setActionMessage('Invoice and associated uploaded file deleted.')
      await refreshHistory(false)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to delete invoice record.')
    } finally {
      setDeletingInvoiceId(null)
    }
  }

  const busy = uploading || processing
  const stats = [
    { label: 'Total invoices', value: invoices.length, icon: 'receipt' as const, tone: 'indigo', foot: 'Records in your workspace' },
    { label: 'Valid invoices', value: validCount, icon: 'check' as const, tone: 'green', foot: 'Passed all required checks' },
    { label: 'Needs review', value: invalidCount, icon: 'alert' as const, tone: 'amber', foot: 'Have one or more errors' },
  ]

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><span /><span /><span /></div><div><strong>Invoice</strong><span>INTELLIGENCE</span></div></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav className="side-nav" aria-label="Main navigation">
        <button className={activeView === 'overview' ? 'nav-item active' : 'nav-item'} onClick={() => setActiveView('overview')}><Icon name="grid" />Overview</button>
        <button className={activeView === 'invoices' ? 'nav-item active' : 'nav-item'} onClick={() => setActiveView('invoices')}><Icon name="file" />Invoices<span className="nav-count">{invoices.length}</span></button>
      </nav>
      <div className="sidebar-bottom"><div className="sidebar-info-icon">i</div><div><strong>Local workspace</strong><span>Files stay on this machine</span></div></div>
    </aside>

    <main className="main-content">
      <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><Icon name="chevron" size={14} /><strong>{activeView === 'overview' ? 'Overview' : 'Invoices'}</strong></div><div className="topbar-actions"><span className="local-indicator"><i />Local API</span><button className="button subtle refresh-button" onClick={() => void refreshHistory()} disabled={historyLoading}><Icon name="refresh" size={16} />Refresh</button></div></header>

      <div className="page-container">
        <div className="page-title-row"><div><p className="eyebrow">INVOICE WORKSPACE</p><h1>{activeView === 'overview' ? 'Invoice overview' : 'All invoices'}</h1><p className="page-subtitle">{activeView === 'overview' ? 'A clear view of your processed invoice documents.' : 'Review, inspect, and manage processed invoice records.'}</p></div>{activeView === 'invoices' && <button className="button primary" onClick={() => document.getElementById('upload-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}><Icon name="upload" size={16} />Upload invoice</button>}</div>

        {historyError && <div className="banner error-banner"><Icon name="alert" size={18} /><span>{historyError}</span><button onClick={() => void refreshHistory()}>Try again</button></div>}
        {actionMessage && <div className={`banner ${actionError ? 'error-banner' : 'success-banner'}`}><Icon name={actionError ? 'alert' : 'check'} size={17} /><span>{actionError || actionMessage}</span><button className="banner-close" onClick={() => { setActionError(''); setActionMessage('') }} aria-label="Dismiss message"><Icon name="close" size={16} /></button></div>}

        {activeView === 'overview' && <>
          <section className="stats-grid" aria-label="Invoice summary">
            {stats.map((stat) => <article className="stat-card" key={stat.label}><div className={`stat-icon ${stat.tone}`}><Icon name={stat.icon} size={19} /></div><div className="stat-main"><span>{stat.label}</span><strong>{historyError ? '—' : historyLoading ? <i className="skeleton-number" /> : stat.value}</strong></div><p>{stat.foot}</p></article>)}
          </section>
          <div className="overview-grid">
            <section className="panel recent-panel"><div className="panel-heading"><div><p className="eyebrow">YOUR DOCUMENTS</p><h2>Recent invoices</h2></div><button className="text-action" onClick={() => setActiveView('invoices')}>View all <Icon name="arrow" size={15} /></button></div>
              <InvoiceHistoryContent loading={historyLoading} error={historyError} invoices={invoices} onView={openInvoice} onDelete={removeInvoice} deletingInvoiceId={deletingInvoiceId} compact />
            </section>
            <UploadPanel file={file} setFile={chooseFile} inputRef={fileInput} busy={busy} uploading={uploading} processing={processing} message={actionMessage} error={actionError} pendingUpload={pendingUpload} result={processingResult} dragging={dragging} setDragging={setDragging} onUpload={handleUpload} onRetry={retryProcessing} onView={(record) => void openInvoice(record.id)} />
          </div>
        </>}

        {activeView === 'invoices' && <>
          <UploadPanel file={file} setFile={chooseFile} inputRef={fileInput} busy={busy} uploading={uploading} processing={processing} message={actionMessage} error={actionError} pendingUpload={pendingUpload} result={processingResult} dragging={dragging} setDragging={setDragging} onUpload={handleUpload} onRetry={retryProcessing} onView={(record) => void openInvoice(record.id)} compact />
          <section className="panel history-panel"><div className="panel-heading"><div><p className="eyebrow">INVOICE REGISTER</p><h2>Invoice history <span className="heading-count">{historyLoading ? '…' : invoices.length}</span></h2></div><button className="button subtle" onClick={() => void refreshHistory()} disabled={historyLoading}><Icon name="refresh" size={16} />Refresh list</button></div>
            <InvoiceHistoryContent loading={historyLoading} error={historyError} invoices={invoices} onView={openInvoice} onDelete={removeInvoice} deletingInvoiceId={deletingInvoiceId} />
          </section>
        </>}
        <footer className="page-footer"><span>Invoice Intelligence</span><span>Deterministic processing · Local SQLite history</span></footer>
      </div>
    </main>

    {detailLoading && <div className="overlay"><div className="loading-detail" role="status"><span className="spinner" />Loading invoice details…</div></div>}
    {selectedInvoice && <InvoiceDetail invoice={selectedInvoice} onClose={() => setSelectedInvoice(null)} onDelete={(invoice) => void removeInvoice(invoice)} deleting={deletingInvoiceId === selectedInvoice.id} />}
  </div>
}

function InvoiceHistoryContent({ loading, error, invoices, onView, onDelete, deletingInvoiceId, compact = false }: { loading: boolean; error: string; invoices: InvoiceRecord[]; onView: (id: number) => void; onDelete: (invoice: InvoiceRecord) => void; deletingInvoiceId: number | null; compact?: boolean }) {
  if (loading) return <div className="loading-state"><span className="spinner" />Loading invoice history…</div>
  if (error && invoices.length === 0) return <div className="empty-state"><div className="empty-icon"><Icon name="alert" size={21} /></div><h3>History unavailable</h3><p>Check the API connection and refresh to try again.</p></div>
  if (invoices.length === 0) return <div className="empty-state"><div className="empty-icon"><Icon name="file" size={21} /></div><h3>No invoices yet</h3><p>Upload a PDF or image to extract fields and see its validation results here.</p></div>
  return <InvoiceTable invoices={invoices} onView={onView} onDelete={onDelete} deletingInvoiceId={deletingInvoiceId} compact={compact} />
}

function UploadPanel({ file, setFile, inputRef, busy, uploading, processing, message, error, pendingUpload, result, dragging, setDragging, onUpload, onRetry, onView, compact = false }: {
  file: File | null
  setFile: (file: File | undefined) => void
  inputRef: RefObject<HTMLInputElement | null>
  busy: boolean
  uploading: boolean
  processing: boolean
  message: string
  error: string
  pendingUpload: InvoiceUploadResponse | null
  result: InvoiceRecord | null
  dragging: boolean
  setDragging: (dragging: boolean) => void
  onUpload: () => void
  onRetry: () => void
  onView: (record: InvoiceRecord) => void
  compact?: boolean
}) {
  const showFeedback = Boolean(message || error)
  return <section className={`panel upload-panel ${compact ? 'upload-panel-compact' : ''}`} id="upload-card">
    <div className="panel-heading upload-heading"><div><p className="eyebrow">GET STARTED</p><h2>Upload an invoice</h2></div><div className="upload-icon"><Icon name="upload" size={19} /></div></div>
    <p className="upload-intro">Add a PDF or image and we’ll extract, validate, and save its invoice details.</p>
    <label className={`dropzone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); setFile(event.dataTransfer.files[0]) }}>
      <input ref={inputRef} type="file" accept="application/pdf,.pdf,image/png,.png,image/jpeg,.jpg,.jpeg" onChange={(event) => setFile(event.target.files?.[0])} />
      <span className="drop-icon"><Icon name={file ? 'file' : 'upload'} size={20} /></span>
      {file ? <><strong>{file.name}</strong><span>{(file.size / (1024 * 1024)).toFixed(2)} MB · {file.type === 'application/pdf' ? 'PDF' : 'Image'}</span></> : <><strong>Drop a PDF or image here</strong><span>or <button type="button" className="browse-inline" onClick={(event) => { event.preventDefault(); event.stopPropagation(); inputRef.current?.click() }}>browse files</button> · PDF, PNG, or JPEG up to 10 MB</span></>}
    </label>
    {busy && <div className="progress-area" role="status"><div className="progress-label"><span>{uploading ? 'Uploading document' : 'Extracting and validating'}</span><span className="spinner small-spinner" /></div><div className="progress-track"><span /></div></div>}
    {showFeedback && <div className={`upload-feedback ${error ? 'feedback-error' : 'feedback-success'}`} role="status"><span className="feedback-icon"><Icon name={error ? 'alert' : processing || uploading ? 'clock' : 'check'} size={15} /></span><span>{error || message}</span></div>}
    {pendingUpload && !busy && <button className="button retry-process" onClick={onRetry}><Icon name="refresh" size={15} />Retry processing</button>}
    <button className="button primary upload-submit" onClick={onUpload} disabled={busy || (!file && !pendingUpload)}>{uploading ? 'Uploading…' : processing ? 'Processing…' : pendingUpload ? 'Process invoice' : 'Upload & process'}<Icon name="arrow" size={16} /></button>
    {result && <div className={`processed-result ${result.is_valid ? 'result-valid' : 'result-invalid'}`}><div className="result-top"><span className="result-check"><Icon name={result.is_valid ? 'check' : 'alert'} size={15} /></span><div><strong>{result.is_valid ? 'Processing complete' : 'Processed with issues'}</strong><span>{result.invoice_number || result.original_filename}</span></div></div><div className="result-bottom"><StatusBadge valid={result.is_valid} /><button className="text-action" onClick={() => onView(result)}>View result <Icon name="arrow" size={14} /></button></div></div>}
    <div className="upload-footnote"><Icon name="clock" size={14} />Your document is stored locally for processing.</div>
  </section>
}
