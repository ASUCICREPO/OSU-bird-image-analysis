import { useState, useEffect } from 'react'
import { list, getUrl, downloadData } from 'aws-amplify/storage'

interface ProcessingResult {
  filename: string
  birdCount: number
  extractionFolder: string
  csvKey: string
  downloadUrl: string
  timestamp: string
}

interface ResultsCheckerProps {
  onResultsFound: (results: ProcessingResult[]) => void
  isProcessing: boolean
}

export function ResultsChecker({ onResultsFound, isProcessing }: ResultsCheckerProps) {
  const [isChecking, setIsChecking] = useState(false)
  const [lastCheck, setLastCheck] = useState<Date | null>(null)

  const checkForResults = async () => {
    if (isChecking) return
    
    setIsChecking(true)
    try {
      console.log('🔍 Checking for new CSV results...')
      
      // List files in the results folder
      const listResult = await list({
        prefix: 'public/results/',
      })
      
      if (!listResult.items) {
        console.log('No results folder found')
        return
      }
      
      // Filter for CSV files and sort by date (newest first)
      const csvFiles = listResult.items
        .filter(item => item.key?.endsWith('.csv'))
        .sort((a, b) => {
          const dateA = a.lastModified || new Date(0)
          const dateB = b.lastModified || new Date(0)
          return dateB.getTime() - dateA.getTime()
        })
      
      console.log(`Found ${csvFiles.length} CSV files`)
      
      if (csvFiles.length === 0) {
        onResultsFound([])
        return
      }
      
      // Process the most recent CSV files (up to 5)
      const recentFiles = csvFiles.slice(0, 5)
      const results: ProcessingResult[] = []
      
      for (const file of recentFiles) {
        if (!file.key) continue
        
        try {
          // Download and parse CSV
          const downloadResult = await downloadData({
            key: file.key
          }).result
          
          const csvText = await downloadResult.body.text()
          const lines = csvText.split('\n').filter(line => line.trim())
          
          if (lines.length < 2) continue // Skip if no data rows
          
          // Parse CSV (skip header)
          const dataLines = lines.slice(1)
          let totalBirds = 0
          let fileCount = 0
          
          for (const line of dataLines) {
            const [filename, birdCount] = line.split(',')
            if (filename && birdCount) {
              totalBirds += parseInt(birdCount) || 0
              fileCount++
            }
          }
          
          // Get download URL
          const urlResult = await getUrl({
            key: file.key,
            options: { expiresIn: 3600 } // 1 hour
          })
          
          // Extract timestamp from filename
          const timestampMatch = file.key.match(/bird-results-(.+)\.csv/)
          const timestamp = timestampMatch ? timestampMatch[1].replace(/-/g, ':') : 'Unknown'
          
          results.push({
            filename: `${fileCount} images processed`,
            birdCount: totalBirds,
            extractionFolder: file.key,
            csvKey: file.key,
            downloadUrl: urlResult.url.toString(),
            timestamp: timestamp
          })
          
        } catch (error) {
          console.error(`Error processing CSV ${file.key}:`, error)
        }
      }
      
      onResultsFound(results)
      setLastCheck(new Date())
      
    } catch (error) {
      console.error('Error checking for results:', error)
    } finally {
      setIsChecking(false)
    }
  }

  // Auto-check for results every 10 seconds when processing
  useEffect(() => {
    if (!isProcessing) return
    
    const interval = setInterval(checkForResults, 10000) // Check every 10 seconds
    
    // Initial check
    checkForResults()
    
    return () => clearInterval(interval)
  }, [isProcessing])

  // Manual check button
  const handleManualCheck = () => {
    checkForResults()
  }

  return (
    <div className="results-checker">
      <div className="check-controls">
        <button 
          onClick={handleManualCheck}
          disabled={isChecking}
          className="check-button"
        >
          {isChecking ? '🔄 Checking...' : '🔍 Check for Results'}
        </button>
        
        {lastCheck && (
          <span className="last-check">
            Last checked: {lastCheck.toLocaleTimeString()}
          </span>
        )}
      </div>
      
      {isProcessing && (
        <div className="auto-check-status">
          <div className="processing-indicator"></div>
          <span>Auto-checking for results every 10 seconds...</span>
        </div>
      )}
    </div>
  )
}