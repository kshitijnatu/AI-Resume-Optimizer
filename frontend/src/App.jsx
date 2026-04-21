import { useState } from 'react'
import Markdown from 'react-markdown'
import './App.css'
import { downloadOptimizedResumes, streamRankApplications } from './api/api'

function App() {
  const [jobDescriptionFiles, setJobDescriptionFiles] = useState([])
  const [singleFile, setSingleFile] = useState(null)
  const [multipleFiles, setMultipleFiles] = useState([])
  const [response, setResponse] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isOptimizing, setIsOptimizing] = useState(false)

  const handleSingleFileChange = (e) => {
    setSingleFile(e.target.files?.[0] ?? null)
  }

  const handleMultipleFilesChange = (e) => {
    setMultipleFiles(Array.from(e.target.files ?? []))
  }

  const handleJobDescriptionFileChange = (e) => {
    setJobDescriptionFiles(Array.from(e.target.files ?? []))
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
      const firstJobDescriptionFile = jobDescriptionFiles[0] ?? null
      await streamRankApplications(candidateFiles, firstJobDescriptionFile, (chunk) => {
        setResponse((prev) => prev + chunk)
      })
    } catch (error) {
      setResponse(error?.message ?? 'Upload failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const handleGenerateOptimizedResumes = async () => {
    const candidateFiles = [...(singleFile ? [singleFile] : []), ...multipleFiles]
    if (candidateFiles.length === 0) {
      setResponse('Please select at least one base resume first.')
      return
    }
    if (jobDescriptionFiles.length === 0) {
      setResponse('Please upload at least one job description PDF first.')
      return
    }

    setIsOptimizing(true)
    try {
      setResponse('Generating optimized resume PDFs. Your download will start automatically...')
      const { blob, filename } = await downloadOptimizedResumes(candidateFiles, jobDescriptionFiles)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      setResponse(`Downloaded ${filename}.`)
    } catch (error) {
      setResponse(error?.message ?? 'Failed to generate optimized resumes. Please try again.')
    } finally {
      setIsOptimizing(false)
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
          <h2>Job descriptions</h2>
          <p className="upload-hint">Upload one or more JD PDFs. One optimized resume is created per JD.</p>
          <form className="upload-form" method="post" encType="multipart/form-data">
            <div className="file-field">
              <span className="file-field-label">JD files</span>
              <input
                className="file-input"
                type="file"
                name="job_description_files"
                multiple
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
        disabled={isLoading || isOptimizing}
      >
          {isLoading ? 'Ranking...' : 'Rank Applications'}
      </button>

      <button
        type="button"
        className="btn btn-primary"
        onClick={handleGenerateOptimizedResumes}
        disabled={isLoading || isOptimizing}
      >
        {isOptimizing ? 'Generating PDFs...' : 'Generate Optimized Resume PDFs'}
      </button>

      <section className="response-panel" aria-live="polite">
        <h2>Response</h2>
        {renderResponse()}
      </section>
    </div>
  )
}

export default App