import { CheckCircle, AlertCircle, Zap, MessageSquare } from 'lucide-react';
import DetectionCard from './DetectionCard';
import VideoPlayer from './VideoPlayer';
import AnalysisDetails from './AnalysisDetails';
import QueryInput from './QueryInput';
import QueryHistory from './QueryHistory';

export default function ResultsView({
  detections,
  stats,
  query,
  videoFile,
  videoInfo,
  seekTimestamp,
  onSeek,
  followUpQuery,
  onFollowUpQueryChange,
  onFollowUpAnalyze,
  queryHistory,
  onSelectHistoryQuery,
}) {
  const hasDetections = detections && detections.length > 0;
  const avgConfidence = hasDetections
    ? Math.round((detections.reduce((sum, d) => sum + d.confidence, 0) / detections.length) * 100)
    : 0;

  return (
    <div className="animate-fade-in">
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left column - Results (60%) */}
        <div className="flex-1 lg:w-3/5 space-y-5">
          {/* Summary */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="flex items-start gap-3">
              {hasDetections ? (
                <div className="w-10 h-10 bg-green-50 rounded-full flex items-center justify-center flex-shrink-0">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                </div>
              ) : (
                <div className="w-10 h-10 bg-orange-50 rounded-full flex items-center justify-center flex-shrink-0">
                  <AlertCircle className="w-5 h-5 text-orange-500" />
                </div>
              )}
              <div>
                <h2 className="text-base font-semibold text-text">
                  {hasDetections
                    ? `Found ${detections.length} detection${detections.length > 1 ? 's' : ''}`
                    : 'No results found'}
                </h2>
                {hasDetections ? (
                  <p className="text-sm text-text-secondary mt-1">
                    Average confidence: <span className="font-medium text-primary-dark">{avgConfidence}%</span>
                    {' • '}Processed {stats?.processed_frames} of {stats?.total_frames?.toLocaleString()} frames in {stats?.time_elapsed}s
                  </p>
                ) : (
                  <p className="text-sm text-text-secondary mt-1">
                    Try rephrasing your query or asking a different question about the video.
                  </p>
                )}
                <div className="flex items-center gap-1.5 mt-2 text-xs text-text-secondary">
                  <MessageSquare className="w-3 h-3" />
                  <span>"{query}"</span>
                </div>
              </div>
            </div>
          </div>

          {/* Detection cards */}
          {hasDetections && (
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-text-secondary flex items-center gap-2">
                <Zap className="w-4 h-4" />
                Detections
              </h3>
              <div className="space-y-2">
                {detections.map((det, i) => (
                  <DetectionCard
                    key={det.id}
                    detection={det}
                    index={i}
                    onClick={onSeek}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Analysis details */}
          <AnalysisDetails stats={stats} />

          {/* Follow-up query */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-text-secondary">Ask a follow-up question</h3>
            <QueryInput
              query={followUpQuery}
              onQueryChange={onFollowUpQueryChange}
              onAnalyze={onFollowUpAnalyze}
              canAnalyze={followUpQuery.trim().length > 0}
            />
          </div>

          {/* Query history */}
          <QueryHistory history={queryHistory} onSelectQuery={onSelectHistoryQuery} />
        </div>

        {/* Right column - Video Player (40%) */}
        <div className="lg:w-2/5">
          <div className="lg:sticky lg:top-6">
            <VideoPlayer
              videoFile={videoFile}
              remoteUrl={videoInfo?.url}
              detections={detections}
              seekTo={seekTimestamp}
              duration={videoInfo?.duration}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
