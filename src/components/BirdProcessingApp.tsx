import { useState, useEffect } from 'react'
import { list, getUrl } from 'aws-amplify/storage'
import { S3FileUploader } from './S3FileUploader'
import { EnhancedCSVViewer } from './EnhancedCSVViewer'

export function BirdProcessingApp() {
  const [enhancedCSVs, setEnhancedCSVs] = useState<any[]>([])
  const [isProcessing, setIsProcessing] = useState(false)

  const handleFileUpload = (_files: File[]) => {
    setIsProcessing(true)
    // Real processing will be triggered by Lambda
    // Poll for results after upload
    setTimeout(() => {
      pollForResults()
    }, 5000)
  }

  const pollForResults = async () => {
    try {
      const result = await list({
        prefix: 'public/results/',
      })
      
      const csvFiles = result.items.filter(item => 
        item.key?.includes('enhanced_bird_results') && item.key?.endsWith('.csv')
      )
      
      const csvData = await Promise.all(
        csvFiles.map(async (file) => {
          const url = await getUrl({ key: file.key! })
          return {
            key: file.key,
            lastModified: file.lastModified,
            downloadUrl: url.url.toString(),
            filename: file.key?.split('/').pop() || 'unknown'
          }
        })
      )
      
      setEnhancedCSVs(csvData.sort((a, b) => 
        new Date(b.lastModified!).getTime() - new Date(a.lastModified!).getTime()
      ))
      setIsProcessing(false)
    } catch (error) {
      console.error('Error polling for results:', error)
      setIsProcessing(false)
    }
  }

  useEffect(() => {
    // Load existing results on component mount
    pollForResults()
  }, [])

  const downloadCSV = (csv: any) => {
    window.open(csv.downloadUrl, '_blank')
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <p className="eyebrow">Bird Processing</p>
          <h1>Bird Upload + Bucket Viewer</h1>
          <p className="subhead">
            Upload a ZIP of bird images and monitor your S3 results in one place.
          </p>
        </div>
      </header>

      <main className="main-content two-panel">
        <section className="panel upload-panel">
          <div className="panel-header">
            <h2>Upload ZIP or Images</h2>
            <span className="panel-badge">Step 1</span>
          </div>
          <S3FileUploader 
            onFileUpload={handleFileUpload}
            isProcessing={isProcessing}
          />
          {isProcessing && (
            <div className="processing-status">
              <div className="processing-spinner"></div>
              <p>Processing images...</p>
            </div>
          )}
        </section>

        <section className="panel bucket-panel">
          <div className="panel-header">
            <h2>Bucket Contents</h2>
            <span className="panel-badge">Step 2</span>
          </div>
          <EnhancedCSVViewer />
        </section>
      </main>
    </div>
  )
}
