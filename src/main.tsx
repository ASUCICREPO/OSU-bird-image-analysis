import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Amplify } from 'aws-amplify'
import '@aws-amplify/ui-react/styles.css'
import '@aws-amplify/ui-react-storage/styles.css'
import App from './App.tsx'
import './index.css'

// Configure Amplify with the generated config
async function configureAmplify() {
  try {
    const config = await import('../amplify_outputs.json')
    Amplify.configure(config.default)
    console.log('✅ Amplify configured successfully')
    console.log('Storage bucket:', config.default.storage?.bucket_name)
  } catch (error) {
    console.error('❌ Failed to load Amplify configuration:', error)
    // Fallback configuration for development
    Amplify.configure({
      Auth: {
        Cognito: {
          userPoolId: 'us-west-2_placeholder',
          userPoolClientId: 'placeholder',
          identityPoolId: 'us-west-2:placeholder',
          allowGuestAccess: true
        }
      },
      Storage: {
        S3: {
          bucket: 'placeholder-bucket',
          region: 'us-west-2'
        }
      }
    })
  }
}

configureAmplify().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})