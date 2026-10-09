import type { ApiError, InvoiceRecord, InvoiceUploadResponse } from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch {
    throw new Error('Could not reach the API. Check that the backend is running and try again.')
  }

  if (!response.ok) {
    let message = `Request failed (${response.status}).`
    try {
      const body = (await response.json()) as ApiError
      if (body.detail) message = body.detail
    } catch {
      // Keep the status-based message when the server response is not JSON.
    }
    throw new Error(message)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function fetchInvoices(): Promise<InvoiceRecord[]> {
  return request<InvoiceRecord[]>('/api/invoices')
}

export function fetchInvoice(invoiceId: number): Promise<InvoiceRecord> {
  return request<InvoiceRecord>(`/api/invoices/${invoiceId}`)
}

export function uploadInvoice(file: File): Promise<InvoiceUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  return request<InvoiceUploadResponse>('/api/invoices/upload', {
    method: 'POST',
    body: form,
  })
}

export function processInvoice(uploadId: string): Promise<InvoiceRecord> {
  return request<InvoiceRecord>(`/api/invoices/${encodeURIComponent(uploadId)}/process`, {
    method: 'POST',
  })
}

export function deleteInvoice(invoiceId: number): Promise<void> {
  return request<void>(`/api/invoices/${invoiceId}`, { method: 'DELETE' })
}
