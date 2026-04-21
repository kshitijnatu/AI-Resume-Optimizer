import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:8000',
});

// export const uploadFile = async (file) => {
//     const formData = new FormData();
//     formData.append('file', file);
//     const response = await api.post('/upload-file', formData);
//     return response.data;
// };

// export const uploadFiles = async (files) => {
//     const formData = new FormData();
//     files.forEach(file => formData.append('files', file));
//     const response = await api.post('/upload-files', formData);
//     return response.data;
// };

// export const rankApplications = async (candidateFiles, jobDescriptionFile) => {
//     const formData = new FormData();
//     candidateFiles.forEach((file) => formData.append('files', file));
//     if (jobDescriptionFile) {
//         formData.append('job_description_file', jobDescriptionFile);
//     }
//     const response = await api.post('/rank-applications', formData);
//     return response.data;
// };

async function readStreamToString(stream) {
    if (!stream || typeof stream.getReader !== 'function') {
        return '';
    }
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let out = '';
    while (true) {
        const { value, done } = await reader.read();
        if (done) {
            break;
        }
        out += decoder.decode(value, { stream: true });
    }
    return out + decoder.decode();
}

export const streamRankApplications = async (
    candidateFiles,
    jobDescriptionFile,
    onChunk,
) => {
    const formData = new FormData();
    candidateFiles.forEach((file) => formData.append('files', file));
    if (jobDescriptionFile) {
        formData.append('job_description_file', jobDescriptionFile);
    }

    const response = await api.post('/rank-applications/stream', formData, {
        adapter: 'fetch',
        responseType: 'stream',
        validateStatus: () => true,
    });

    if (response.status < 200 || response.status >= 300) {
        const raw = await readStreamToString(response.data);
        let message = 'Streaming request failed.';
        try {
            const errorBody = JSON.parse(raw);
            const detail = errorBody?.detail;
            if (detail != null) {
                message = typeof detail === 'string' ? detail : JSON.stringify(detail);
            } else if (raw) {
                message = raw;
            }
        } catch {
            if (raw) {
                message = raw;
            }
        }
        throw new Error(message);
    }

    const body = response.data;
    if (!body || typeof body.getReader !== 'function') {
        throw new Error('Streaming response body is not available.');
    }

    const reader = body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { value, done } = await reader.read();
        if (done) {
            break;
        }
        onChunk(decoder.decode(value, { stream: true }));
    }

    const tail = decoder.decode();
    if (tail) {
        onChunk(tail);
    }
};