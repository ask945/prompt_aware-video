function buildHeaders(token, extraHeaders = {}) {
  return {
    ...extraHeaders,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function parseResponse(response, fallbackMessage) {
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw new Error(data?.detail || fallbackMessage);
  }

  return data;
}

function normalizeVideo(video, fallbackFile = null) {
  const duration = Number(video?.duration || 0);

  return {
    ...video,
    video_id: video?.video_id || video?.public_id,
    filename: video?.filename || fallbackFile?.name || 'Untitled video',
    size: video?.bytes || fallbackFile?.size || 0,
    duration,
    total_frames: Math.max(1, Math.round(duration * 30)),
  };
}

export async function signup({ email, password }) {
  const response = await fetch('/api/auth/signup', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  return parseResponse(response, 'Sign up failed.');
}

export async function login({ email, password }) {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });

  return parseResponse(response, 'Login failed.');
}

export async function fetchCurrentUser(token) {
  const response = await fetch('/api/auth/me', {
    headers: buildHeaders(token),
  });

  return parseResponse(response, 'Unable to load your session.');
}

export async function logout(token) {
  const response = await fetch('/api/auth/logout', {
    method: 'POST',
    headers: buildHeaders(token),
  });

  return parseResponse(response, 'Logout failed.');
}

export async function fetchVideos(token) {
  const response = await fetch('/api/videos', {
    headers: buildHeaders(token),
  });

  const data = await parseResponse(response, 'Failed to load videos.');
  return (data?.videos || []).map((video) => normalizeVideo(video));
}

export async function uploadVideo(file, token) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/upload', {
    method: 'POST',
    headers: buildHeaders(token),
    body: formData,
  });

  const data = await parseResponse(response, 'Upload failed.');
  return normalizeVideo(data, file);
}

export async function fetchResults(token, jobId) {
  const response = await fetch(`/api/results/${jobId}`, {
    headers: buildHeaders(token),
  });

  return parseResponse(response, 'Failed to fetch results.');
}

export async function analyzeVideo({ token, videoId, videoUrl, query }) {
  const response = await fetch('/api/analyze', {
    method: 'POST',
    headers: buildHeaders(token, {
      'Content-Type': 'application/json',
    }),
    body: JSON.stringify({
      video_id: videoId,
      video_url: videoUrl,
      query,
    }),
  });

  return parseResponse(response, 'Failed to start analysis.');
}
