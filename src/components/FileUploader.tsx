import { useState, useRef } from 'react'

interface FileUploaderProps {
  onFileUpload: (files: File[]) => void
  isProcessing: boolean
}

export function FileUploader({ onFileUpload, isProcessing }: FileUploaderProps) {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    const files = Array.from(e.dataTransfer.files)
    handleFiles(files)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    handleFiles(files)
  }

  const handleFiles = (files: File[]) => {
    // Filter for ZIP files and images
    const validFiles = files.filter(file => 
      file.type === 'application/zip' || 
      file.type === 'application/x-zip-compressed' ||
      file.type.startsWith('image/')
    )
    
    setSelectedFiles(validFiles)
  }

  const handleUpload = () => {
    if (selectedFiles.length > 0) {
      onFileUpload(selectedFiles)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div className="file-uploader">
      <h2>📁 Upload Bird Images</h2>
      <p className="upload-description">
        Upload ZIP files containing bird images or individual image files (JPG, PNG, GIF, BMP)
      </p>

      <div 
        className={`upload-zone ${dragActive ? 'drag-active' : ''} ${isProcessing ? 'processing' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".zip,.jpg,.jpeg,.png,.gif,.bmp"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          disabled={isProcessing}
        />

        <div className="upload-content">
          {isProcessing ? (
            <>
              <div className="processing-spinner"></div>
              <h3>Processing Images...</h3>
              <p>AI is analyzing your bird images</p>
            </>
          ) : (
            <>
              <div className="upload-icon">📤</div>
              <h3>Drop files here or click to browse</h3>
              <p>Supports ZIP files and images (JPG, PNG, GIF, BMP)</p>
              <p className="file-limit">Maximum file size: 100MB</p>
            </>
          )}
        </div>
      </div>

      {selectedFiles.length > 0 && !isProcessing && (
        <div className="selected-files">
          <h3>Selected Files ({selectedFiles.length})</h3>
          <div className="file-list">
            {selectedFiles.map((file, index) => (
              <div key={index} className="file-item">
                <span className="file-name">{file.name}</span>
                <span className="file-size">{formatFileSize(file.size)}</span>
                <span className="file-type">{file.type.includes('zip') ? 'ZIP' : 'Image'}</span>
              </div>
            ))}
          </div>
          
          <button 
            onClick={handleUpload}
            className="upload-button"
            disabled={isProcessing}
          >
            🚀 Start Processing
          </button>
        </div>
      )}
    </div>
  )
}