import { useState, useCallback } from 'react'

const SUPPORTED_TYPES = ['video/mp4', 'video/avi', 'video/x-msvideo', 'video/quicktime', 'video/webm']
const MAX_SIZE = 100 * 1024 * 1024 // 100MB

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export function useVideoUpload() {
  const [video, setVideo] = useState(null)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)

  const processFile = useCallback((file) => {
    setError(null)

    if (!SUPPORTED_TYPES.includes(file.type) && !file.name.match(/\.(mp4|avi|mov|webm)$/i)) {
      setError('Unsupported format. Please use MP4, AVI, MOV, or WebM.')
      return
    }

    if (file.size > MAX_SIZE) {
      setError('File too large. Maximum size is 100MB.')
      return
    }

    setUploading(true)
    setUploadProgress(0)

    // Extract local metadata (thumbnail, dimensions) while uploading
    const localUrl = URL.createObjectURL(file)
    const videoEl = document.createElement('video')
    videoEl.preload = 'metadata'

    let localMeta = null

    const metaPromise = new Promise((resolve) => {
      videoEl.onloadedmetadata = () => {
        videoEl.currentTime = Math.min(1, videoEl.duration / 4)
      }
      videoEl.onseeked = () => {
        const canvas = document.createElement('canvas')
        canvas.width = 320
        canvas.height = 180
        const ctx = canvas.getContext('2d')
        ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height)
        const thumbnail = canvas.toDataURL('image/jpeg', 0.7)
        localMeta = {
          thumbnail,
          duration: videoEl.duration,
          durationFormatted: formatDuration(videoEl.duration),
          width: videoEl.videoWidth,
          height: videoEl.videoHeight,
        }
        resolve()
      }
      videoEl.onerror = () => resolve() // don't block upload on meta extraction failure
      videoEl.src = localUrl
    })

    // Upload to backend (which uploads to Cloudinary)
    const formData = new FormData()
    formData.append('file', file)

    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/upload')

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setUploadProgress(Math.round((e.loaded / e.total) * 90))
      }
    }

    xhr.onload = async () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const data = JSON.parse(xhr.responseText)
        setUploadProgress(95)

        // Wait for local metadata extraction to finish
        await metaPromise
        setUploadProgress(100)

        setTimeout(() => {
          setVideo({
            file,
            name: file.name,
            size: formatFileSize(file.size),
            duration: localMeta?.duration || data.duration || 0,
            durationFormatted: localMeta?.durationFormatted || formatDuration(data.duration || 0),
            url: localUrl,
            cloudinaryUrl: data.url,
            publicId: data.public_id,
            thumbnail: localMeta?.thumbnail || '',
            width: localMeta?.width || data.width || 0,
            height: localMeta?.height || data.height || 0,
          })
          setUploading(false)
          setUploadProgress(0)
        }, 300)
      } else {
        let msg = 'Upload failed.'
        try {
          const err = JSON.parse(xhr.responseText)
          msg = err.detail || msg
        } catch {}
        setError(msg)
        setUploading(false)
        setUploadProgress(0)
        URL.revokeObjectURL(localUrl)
      }
    }

    xhr.onerror = () => {
      setError('Upload failed. Check your connection and try again.')
      setUploading(false)
      setUploadProgress(0)
      URL.revokeObjectURL(localUrl)
    }

    xhr.send(formData)
  }, [])

  const removeVideo = useCallback(() => {
    if (video?.url) URL.revokeObjectURL(video.url)
    setVideo(null)
    setError(null)
  }, [video])

  return { video, error, uploading, uploadProgress, processFile, removeVideo, setError }
}
