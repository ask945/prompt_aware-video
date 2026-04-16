import { useCallback, useEffect, useRef, useState } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import {
  analyzeVideo,
  fetchCurrentUser,
  fetchResults,
  fetchVideos,
  login,
  logout,
  signup,
  uploadVideo,
} from './api/videoApi';
import AuthCard from './components/AuthCard';
import Header from './components/Header';
import ProcessingView from './components/ProcessingView';
import QueryInput from './components/QueryInput';
import ResultsView from './components/ResultsView';
import RetryCard from './components/RetryCard';
import UploadZone from './components/UploadZone';
import VideoLibrary from './components/VideoLibrary';

const SESSION_KEY = 'prompt-aware-session-token';

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(SESSION_KEY) || '');
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  const [videoFile, setVideoFile] = useState(null);
  const [videoInfo, setVideoInfo] = useState(null);
  const [videos, setVideos] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [query, setQuery] = useState('');
  const [analyzing, setAnalyzing] = useState(false);

  // Results state
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null); // 'processing' | 'complete' | 'failed'
  const [jobProgress, setJobProgress] = useState(0);
  const [jobStats, setJobStats] = useState(null);
  const [detections, setDetections] = useState([]);
  const [jobError, setJobError] = useState(null);
  const [seekTimestamp, setSeekTimestamp] = useState(null);
  const [followUpQuery, setFollowUpQuery] = useState('');
  const [queryHistory, setQueryHistory] = useState([]);
  const pollingRef = useRef(null);

  useEffect(() => {
    async function restoreSession() {
      if (!token) {
        setAuthReady(true);
        return;
      }

      try {
        const response = await fetchCurrentUser(token);
        setUser(response.user);
        const storedVideos = await fetchVideos(token);
        setVideos(storedVideos);
        setVideoInfo((current) => current || storedVideos[0] || null);
      } catch {
        localStorage.removeItem(SESSION_KEY);
        setToken('');
        setUser(null);
      } finally {
        setAuthReady(true);
      }
    }

    restoreSession();
  }, [token]);

  // ─── Poll for results ───
  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (activeJobId) => {
      stopPolling();
      pollingRef.current = setInterval(async () => {
        try {
          const data = await fetchResults(token, activeJobId);

          if (data.status === 'processing') {
            setJobProgress(data.progress || 0);
            setJobStats({
              processed_frames: data.frames_processed || 0,
              total_frames: data.total_frames || 0,
              strategy: data.strategy,
              modules: data.modules || [],
              time_elapsed: 0,
            });
            return;
          }

          // Terminal state — stop polling
          stopPolling();

          if (data.status === 'complete') {
            setJobStatus('complete');
            setDetections(
              (data.detections || []).map((d, i) => ({
                id: `det-${i}`,
                label: d.text_content || d.object_class || 'Detection',
                confidence: d.confidence || 0,
                timestamp: d.timestamp || 0,
                timestamp_fmt: d.timestamp_fmt || '',
                frame_number: d.frame_number,
                color: d.color,
                bbox: d.bbox,
                frame_url: d.frame_url,
                text_content: d.text_content,
              }))
            );
            setJobStats({
              processed_frames: data.stats?.frames_processed || 0,
              total_frames: data.stats?.total_frames || 0,
              time_elapsed: data.stats?.time_taken ? data.stats.time_taken.toFixed(1) : '0',
              strategy: data.stats?.strategy,
              modules: data.stats?.modules || [],
              intent: data.stats?.intent,
              target: data.stats?.target,
              attribute: data.stats?.attribute,
              temporal_scope: data.stats?.temporal_scope,
            });
            setQueryHistory((prev) => [
              { query, found: data.found, count: data.detection_count || 0 },
              ...prev,
            ]);
            setAnalyzing(false);
            toast.success(
              data.found
                ? `Found ${data.detection_count} detection${data.detection_count > 1 ? 's' : ''}!`
                : 'Analysis complete — no detections found.'
            );
          } else if (data.status === 'failed') {
            setJobStatus('failed');
            setJobError(data.error || 'Analysis failed.');
            setAnalyzing(false);
            toast.error(data.error || 'Analysis failed.');
          }
        } catch {
          stopPolling();
          setJobStatus('failed');
          setJobError('Lost connection while polling results.');
          setAnalyzing(false);
        }
      }, 2000);
    },
    [token, query, stopPolling]
  );

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const resetResults = useCallback(() => {
    stopPolling();
    setJobId(null);
    setJobStatus(null);
    setJobProgress(0);
    setJobStats(null);
    setDetections([]);
    setJobError(null);
    setSeekTimestamp(null);
    setFollowUpQuery('');
  }, [stopPolling]);

  const handleAuthSubmit = async (event) => {
    event.preventDefault();
    setAuthLoading(true);

    try {
      const action = authMode === 'login' ? login : signup;
      const response = await action({ email, password });

      localStorage.setItem(SESSION_KEY, response.token);
      setToken(response.token);
      setUser(response.user);
      setVideos([]);
      setVideoInfo(null);
      setVideoFile(null);
      setQuery('');
      setPassword('');
      toast.success(authMode === 'login' ? 'Signed in successfully.' : 'Account created successfully.');
    } catch (error) {
      toast.error(error.message || 'Authentication failed.');
    } finally {
      setAuthLoading(false);
    }
  };

  const refreshVideos = async (sessionToken) => {
    const storedVideos = await fetchVideos(sessionToken);
    setVideos(storedVideos);
    return storedVideos;
  };

  const handleUpload = async (file) => {
    setUploading(true);

    try {
      const info = await uploadVideo(file, token);
      setVideoFile(file);
      setVideoInfo(info);
      const storedVideos = await refreshVideos(token);
      const freshSelection = storedVideos.find((video) => video.video_id === info.video_id) || info;
      setVideoInfo(freshSelection);
      toast.success('Video uploaded successfully!');
    } catch (error) {
      toast.error(error.message || 'Failed to upload video. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const handleSelectVideo = (selectedVideo) => {
    setVideoFile(null);
    setVideoInfo(selectedVideo);
  };

  const handleRemoveVideo = () => {
    setVideoFile(null);
    setVideoInfo(null);
    setQuery('');
  };

  const handleAnalyze = async (overrideQuery) => {
    const activeQuery = (overrideQuery || query).trim();

    if (!videoInfo?.url) {
      toast.error('Please select or upload a video first.');
      return;
    }

    if (!activeQuery) {
      toast.error('Please enter a prompt first.');
      return;
    }

    resetResults();
    setAnalyzing(true);
    setJobStatus('processing');
    setJobProgress(0);

    try {
      const data = await analyzeVideo({
        token,
        videoId: videoInfo.video_id,
        videoUrl: videoInfo.url,
        query: activeQuery,
      });

      setJobId(data.job_id);
      startPolling(data.job_id);
    } catch (error) {
      toast.error(error.message || 'Failed to start analysis.');
      setAnalyzing(false);
      setJobStatus(null);
    }
  };

  const handleCancelAnalysis = () => {
    resetResults();
    setAnalyzing(false);
  };

  const handleFollowUpAnalyze = () => {
    setQuery(followUpQuery);
    handleAnalyze(followUpQuery);
    setFollowUpQuery('');
  };

  const handleSeek = (timestamp) => {
    setSeekTimestamp({ time: timestamp, key: Date.now() });
  };

  const handleBackToUpload = () => {
    resetResults();
    setQuery('');
  };

  const handleLogout = async () => {
    try {
      if (token) {
        await logout(token);
      }
    } catch {
      // Keep logout resilient even if the backend request fails.
    } finally {
      localStorage.removeItem(SESSION_KEY);
      setToken('');
      setUser(null);
      setVideos([]);
      setVideoFile(null);
      setVideoInfo(null);
      setQuery('');
      setEmail('');
      setPassword('');
    }
  };

  return (
    <div className="min-h-screen bg-bg">
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#FFFFFF',
            color: '#111827',
            fontSize: '14px',
            border: '1px solid #E5E7EB',
            borderRadius: '12px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
          },
          success: {
            iconTheme: { primary: '#7CCF3B', secondary: '#fff' },
          },
          error: {
            iconTheme: { primary: '#EF4444', secondary: '#fff' },
          },
        }}
      />

      <Header user={user} onLogout={handleLogout} />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        {!authReady ? (
          <div className="max-w-md mx-auto rounded-2xl border border-border bg-card px-6 py-10 text-center text-sm text-text-secondary">
            Restoring your session...
          </div>
        ) : !user ? (
          <AuthCard
            mode={authMode}
            email={email}
            password={password}
            loading={authLoading}
            onModeChange={setAuthMode}
            onEmailChange={setEmail}
            onPasswordChange={setPassword}
            onSubmit={handleAuthSubmit}
          />
        ) : jobStatus === 'processing' ? (
            <ProcessingView
              query={query}
              videoInfo={videoInfo}
              progress={jobProgress}
              stats={jobStats}
              onCancel={handleCancelAnalysis}
            />
          ) : jobStatus === 'complete' ? (
            <div className="space-y-4">
              <button
                onClick={handleBackToUpload}
                className="text-sm text-primary-dark hover:text-primary font-medium"
              >
                &larr; Back to videos
              </button>
              <ResultsView
                detections={detections}
                stats={jobStats}
                query={query}
                videoFile={videoFile}
                videoInfo={videoInfo}
                seekTimestamp={seekTimestamp}
                onSeek={handleSeek}
                followUpQuery={followUpQuery}
                onFollowUpQueryChange={setFollowUpQuery}
                onFollowUpAnalyze={handleFollowUpAnalyze}
                queryHistory={queryHistory}
                onSelectHistoryQuery={(q) => {
                  setQuery(q);
                  handleAnalyze(q);
                }}
              />
            </div>
          ) : jobStatus === 'failed' ? (
            <div className="space-y-4">
              <button
                onClick={handleBackToUpload}
                className="text-sm text-primary-dark hover:text-primary font-medium"
              >
                &larr; Back to videos
              </button>
              <RetryCard
                message={jobError}
                onRetry={() => handleAnalyze()}
              />
            </div>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
              <section className="space-y-6 animate-fade-in">
                <div className="rounded-2xl bg-card border border-border p-6">
                  <div className="mb-8">
                    <h2 className="text-2xl font-bold text-text">Upload a new video</h2>
                    <p className="text-sm text-text-secondary mt-2">
                      New uploads are saved to your account and added to your reusable video library.
                    </p>
                  </div>

                  <UploadZone
                    videoFile={videoFile}
                    videoInfo={videoInfo}
                    uploading={uploading}
                    onUpload={handleUpload}
                    onRemove={handleRemoveVideo}
                  />
                </div>

                <div className="rounded-2xl bg-card border border-border p-6">
                  <div className="mb-4">
                    <h3 className="text-lg font-semibold text-text">Analyze selected video</h3>
                    <p className="text-sm text-text-secondary mt-1">
                      {videoInfo
                        ? `Selected: ${videoInfo.filename}`
                        : 'Choose a video from your library or upload a new one.'}
                    </p>
                  </div>

                  <QueryInput
                    query={query}
                    onQueryChange={setQuery}
                    onAnalyze={handleAnalyze}
                    disabled={uploading || analyzing || !videoInfo}
                    canAnalyze={Boolean(videoInfo) && query.trim().length > 0 && !analyzing}
                  />
                </div>
              </section>

              <VideoLibrary
                videos={videos}
                selectedVideoId={videoInfo?.video_id || null}
                onSelect={handleSelectVideo}
              />
            </div>
          )}
      </main>
    </div>
  );
}
