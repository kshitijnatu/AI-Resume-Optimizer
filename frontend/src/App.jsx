import { useState } from 'react'
import Markdown from 'react-markdown'
import './App.css'
import { streamRankApplications } from './api/api'

function App() {
  const [jobDescriptionFile, setJobDescriptionFile] = useState(null)
  const [singleFile, setSingleFile] = useState(null)
  const [multipleFiles, setMultipleFiles] = useState([])
  const [response, setResponse] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSingleFileChange = (e) => {
    setSingleFile(e.target.files?.[0] ?? null)
  }

  const handleMultipleFilesChange = (e) => {
    setMultipleFiles(Array.from(e.target.files ?? []))
  }

  const handleJobDescriptionFileChange = (e) => {
    setJobDescriptionFile(e.target.files?.[0] ?? null)
  }

  const handleRankApplications = async () => {
    const candidateFiles = [...(singleFile ? [singleFile] : []), ...multipleFiles]
    if (candidateFiles.length === 0) {
      setResponse('Please select at least one candidate resume first.')
      return
    }

    setIsLoading(true)
    try {
      setResponse('')
      await streamRankApplications(candidateFiles, jobDescriptionFile, (chunk) => {
        setResponse((prev) => prev + chunk)
      })
    } catch (error) {
      setResponse(error?.message ?? 'Upload failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const renderResponse = () => {
    if (response === '') {
      return (
        <p className="response-body response-placeholder">
          Upload a PDF to see extracted text here.
        </p>
      )
    }

    if (Array.isArray(response)) {
      return (
        <ul className="response-list">
          {response.map((text, i) => (
            <li key={i} className="response-item">
              <span className="response-item-title">File {i + 1}</span>
              <div className="markdown-content">
                <Markdown>{text}</Markdown>
              </div>
            </li>
          ))}
        </ul>
      )
    }

    return (
      <div className="response-body">
        <div className="markdown-content">
          <Markdown>{String(response)}</Markdown>
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">AI Resume Ranker</h1>
        <p className="app-lede">
          Upload resumes and job description to rank the applications.
        </p>
      </header>

      <div className="app-grid">
        <section className="upload-card">
          <h2>Job description</h2>
          <p className="upload-hint">Upload one JD file used only as scoring criteria.</p>
          <form className="upload-form" method="post" encType="multipart/form-data">
            <div className="file-field">
              <span className="file-field-label">JD file (optional)</span>
              <input
                className="file-input"
                type="file"
                name="job_description_file"
                accept=".pdf,application/pdf"
                onChange={handleJobDescriptionFileChange}
              />
            </div>
          </form>
        </section>

        <section className="upload-card">
          <h2>Single resume</h2>
          <p className="upload-hint">Choose one candidate resume PDF.</p>
          <form className="upload-form" method="post" encType="multipart/form-data">
            <div className="file-field">
              <span className="file-field-label">Resume file</span>
              <input
                className="file-input"
                type="file"
                name="file"
                accept=".pdf,application/pdf"
                onChange={handleSingleFileChange}
              />
            </div>
          </form>
        </section>

        <section className="upload-card">
          <h2>Multiple resumes</h2>
          <p className="upload-hint">Select several candidate resume PDFs.</p>
          <form className="upload-form" method="post" encType="multipart/form-data">
            <div className="file-field">
              <span className="file-field-label">Resume files</span>
              <input
                className="file-input"
                type="file"
                name="files"
                multiple
                accept=".pdf,application/pdf"
                onChange={handleMultipleFilesChange}
              />
            </div>
          </form>
        </section>
      </div>

      <button 
        type="button" 
        className="btn btn-primary" 
        onClick={handleRankApplications} 
        disabled={isLoading}
      >
          {isLoading ? 'Ranking...' : 'Rank Applications'}
      </button>

      <section className="response-panel" aria-live="polite">
        <h2>Response</h2>
        {renderResponse()}
      </section>
    </div>
  )
}

export default App