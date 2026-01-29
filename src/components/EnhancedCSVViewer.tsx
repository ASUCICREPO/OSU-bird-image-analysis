import { useState, useEffect } from 'react'
import { list, getUrl } from 'aws-amplify/storage'

interface CSVFile {
  path: string
  lastModified?: Date
  size?: number
  downloadUrl?: string
}

export function EnhancedCSVViewer() {
  const [csvFiles, setCsvFiles] = useState<CSVFile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadCSVFiles = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // List files in the results folder
      const result = await list({
        path: 'public/results/',
        options: {
          listAll: true
        }
      })
      
      // Filter for enhanced CSV files
      const enhancedCSVs = result.items.filter(item => 
        item.path?.includes('enhanced_bird_results') && item.path?.endsWith('.csv')
      )
      
      // Get download URLs for each CSV
      const csvsWithUrls = await Promise.all(
        enhancedCSVs.map(async (csv) => {
          try {
            const url = await getUrl({ 
              path: csv.path!,
              options: {
                expiresIn: 3600 // 1 hour
              }
            })
            return {
              ...csv,
              downloadUrl: url.url.toString()
            }
          } catch (err) {
            console.error(`Failed to get URL for ${csv.path}:`, err)
            return csv
          }
        })
      )
      
      // Sort by last modified (newest first)
      csvsWithUrls.sort((a, b) => 
        new Date(b.lastModified!).getTime() - new Date(a.lastModified!).getTime()
      )
      
      setCsvFiles(csvsWithUrls)
    } catch (err) {
      console.error('Error loading CSV files:', err)
      setError('Failed to load enhanced CSV files. Make sure some processing has completed.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCSVFiles()
    // Refresh every 30 seconds to check for new files
    const interval = setInterval(loadCSVFiles, 30000)
    return () => clearInterval(interval)
  }, [])

  const downloadCSV = (csv: CSVFile) => {
    if (csv.downloadUrl) {
      window.open(csv.downloadUrl, '_blank')
    } else {
      alert('Download URL not available for this file')
    }
  }

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'Unknown'
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  const getFileName = (path: string) => {
    return path.split('/').pop() || path
  }

  if (loading) {
    return (
      <div className="csv-viewer-loading">
        <div className="processing-spinner"></div>
        <p>Loading enhanced CSV files...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="csv-viewer-error">
        <p>{error}</p>
        <button onClick={loadCSVFiles} className="retry-button">
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="enhanced-csv-viewer">
      <div className="csv-header">
        <h3>Enhanced CSV Results ({csvFiles.length})</h3>
        <button onClick={loadCSVFiles} className="refresh-button">
          Refresh
        </button>
      </div>

      {csvFiles.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">No files</div>
          <h4>No enhanced results yet</h4>
          <p>Upload bird images to generate AI-enhanced CSV results</p>
        </div>
      ) : (
        <div className="csv-list">
          {csvFiles.map((csv, index) => (
            <div key={index} className="csv-item">
              <div className="csv-info">
                <div className="csv-name">
                  {getFileName(csv.path)}
                </div>
                <div className="csv-details">
                  <span className="csv-date">
                    {csv.lastModified?.toLocaleString()}
                  </span>
                  <span className="csv-size">
                    {formatFileSize(csv.size)}
                  </span>
                </div>
              </div>
              
              <button 
                onClick={() => downloadCSV(csv)}
                className="download-button"
                disabled={!csv.downloadUrl}
              >
                Download
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
