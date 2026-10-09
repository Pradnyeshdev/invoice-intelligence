export type ValidationCheck = {
  name: string
  status: 'passed' | 'failed' | 'warning' | 'skipped'
  message: string
}

export type InvoiceUploadResponse = {
  upload_id: string
  original_filename: string
  content_type: string
  file_size: number
  status: string
}

export type InvoiceRecord = {
  id: number
  upload_id: string
  original_filename: string
  invoice_number: string | null
  invoice_date: string | null
  vendor_name: string | null
  subtotal: string | null
  tax: string | null
  total: string | null
  currency: string | null
  is_valid: boolean
  errors: string[]
  warnings: string[]
  checks: ValidationCheck[]
  created_at: string
}

export type ApiError = {
  detail?: string
}
