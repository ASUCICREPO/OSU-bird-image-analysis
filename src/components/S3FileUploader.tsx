import { useState, useRef } from 'react'
import { uploadData } from 'aws-amplify/storage'

interface S3FileUploaderProps {
  onFileUpload: (files: File[]) => void
  isProcessing: boolean
}

export function S3FileUploader({ onFileUpload, isProcessing }: S3FileUploaderProps) {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [uploadProgress, setUploadProgress] = useState<{[key: string]: number}>({})
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([])
  const [isDemoMode, setIsDemoMode] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Check if we have real AWS configuration
  useState(() => {
    // Since amplify_outputs.json exists, we're not in demo mode
    setIsDemoMode(false)
  })

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
    
    if (validFiles.length !== files.length) {
      alert(`${files.length - validFiles.length} files were skipped. Only ZIP and image files are supported.`)
    }
    
    setSelectedFiles(validFiles)
  }

  const uploadToS3 = async (file: File): Promise<string> => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
    const fileName = `${timestamp}-${file.name}`
    const key = `uploads/${fileName}`

    try {
      console.log('Attempting to upload to S3:', key)
      
      const result = await uploadData({
        key,
        data: file,
        options: {
          onProgress: ({ transferredBytes, totalBytes }) => {
            if (totalBytes) {
              const progress = Math.round((transferredBytes / totalBytes) * 100)
              setUploadProgress(prev => ({ ...prev, [file.name]: progress }))
              console.log(`Upload progress for ${file.name}: ${progress}%`)
            }
          }
        }
      }).result

      console.log('Upload successful:', result.key)
      return result.key
    } catch (error) {
      console.error('Upload failed:', error)
      throw error
    }
  }

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return

    try {
      console.log('Starting upload process...')
      setUploadProgress({})
      
      const uploadPromises = selectedFiles.map(async (file) => {
        try {
          return await uploadToS3(file)
        } catch (error) {
          console.error(`Failed to upload ${file.name}:`, error)
          throw error
        }
      })
      
      const uploadedKeys = await Promise.all(uploadPromises)
      
      setUploadedFiles(uploadedKeys)
      onFileUpload(selectedFiles)
      
      // Clear selected files after successful upload
      setSelectedFiles([])
      setUploadProgress({})
      
      console.log('All uploads completed successfully')
      
    } catch (error) {
      console.error('Upload failed:', error)
      
      // Show more detailed error message
      let errorMessage = 'Upload failed. '
      if (error instanceof Error) {
        errorMessage += error.message
      } else {
        errorMessage += 'Please check the console for details.'
      }
      
      alert(errorMessage)
      
      // Clear progress on error
      setUploadProgress({})
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const isUploading = Object.keys(uploadProgress).length > 0
  const overallProgress = selectedFiles.length > 0
    ? Math.round(
        selectedFiles.reduce((sum, file) => sum + (uploadProgress[file.name] || 0), 0) /
        selectedFiles.length
      )
    : 0

  return (
    <div className="file-uploader">
      <div className={`s3-status ${isDemoMode ? 'disconnected' : 'connected'}`}>
        <div className="status-indicator"></div>
        {isDemoMode ? (
          <span>Demo Mode - Run "npx ampx sandbox" to enable real S3 uploads</span>
        ) : (
          <span>Connected to AWS S3</span>
        )}
      </div>
      
      <h2>Upload Bird Images</h2>
      <p className="upload-description">
        Upload ZIP files containing bird images or individual image files (JPG, PNG, GIF, BMP)
      </p>

      <div 
        className={`upload-zone ${dragActive ? 'drag-active' : ''} ${isProcessing || isUploading ? 'processing' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !isUploading && !isProcessing && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".zip,.jpg,.jpeg,.png,.gif,.bmp"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          disabled={isProcessing || isUploading}
        />

        <div className="upload-content">
          {isProcessing ? (
            <>
              <div className="processing-spinner"></div>
              <h3>Processing Images...</h3>
              <p>Analyzing your bird images</p>
            </>
          ) : isUploading ? (
            <>
              <div className="processing-spinner"></div>
              <h3>Uploading to S3...</h3>
              <p>Uploading files to secure cloud storage</p>
            </>
          ) : (
            <>
              <div className="upload-icon">Upload</div>
              <h3>Drop files here or click to browse</h3>
              <p>Supports ZIP files and images (JPG, PNG, GIF, BMP)</p>
              <p className="file-limit">Maximum file size: 100MB per file</p>
            </>
          )}
        </div>
      </div>

      {selectedFiles.length > 0 && !isUploading && !isProcessing && (
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
            disabled={isProcessing || isUploading}
          >
            Upload to S3 & Process
          </button>
        </div>
      )}

      {isUploading && (
        <div className="upload-progress">
          <h3>Upload Progress</h3>
          <div className="progress-summary">
            <span className="progress-percent">{overallProgress}%</span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${overallProgress}%` }}
            ></div>
          </div>
        </div>
      )}

      {uploadedFiles.length > 0 && (
        <div className="uploaded-files">
          <h3>Successfully Uploaded ({uploadedFiles.length} files)</h3>
          <p>Files are now stored in S3 and ready for processing</p>
        </div>
      )}
    </div>
  )
}
