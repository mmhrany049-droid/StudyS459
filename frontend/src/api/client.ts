import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default apiClient

// API functions
export const authAPI = {
  login: (username: string, password: string) => apiClient.post('/auth/login', { username, password }),
  register: (data: any) => apiClient.post('/auth/register', data),
  me: () => apiClient.get('/auth/me')
}

export const booksAPI = {
  listSubjects: () => apiClient.get('/books/subjects'),
  listBooks: (params?: any) => apiClient.get('/books/', { params }),
  getBook: (id: number) => apiClient.get(`/books/${id}`),
  getNodes: (bookId: number) => apiClient.get(`/books/${bookId}/nodes`),
  getTestSets: (bookId: number, nodeId?: number) => apiClient.get(`/books/${bookId}/test-sets`, { params: { node_id: nodeId } }),
  getQuestions: (bookId: number, params?: any) => apiClient.get(`/books/${bookId}/questions`, { params }),
  getActivations: () => apiClient.get('/books/activations/me'),
  activate: (bookId: number, isActive: boolean = true) => apiClient.post(`/books/${bookId}/activate`, null, { params: { is_active: isActive } })
}

export const testAPI = {
  createSession: (data: any) => apiClient.post('/test-sessions/', data),
  listSessions: (params?: any) => apiClient.get('/test-sessions/', { params }),
  getSession: (id: number) => apiClient.get(`/test-sessions/${id}`),
  submitAnswer: (sessionId: number, data: any) => apiClient.post(`/test-sessions/${sessionId}/answer`, data),
  submitBatch: (sessionId: number, data: any) => apiClient.post(`/test-sessions/${sessionId}/answers/batch`, data),
  finish: (sessionId: number, data: any) => apiClient.post(`/test-sessions/${sessionId}/finish`, data),
  getResult: (sessionId: number) => apiClient.get(`/test-sessions/${sessionId}/result`),
  getHistory: (questionId: number) => apiClient.get(`/test-sessions/questions/${questionId}/history`)
}

export const analyticsAPI = {
  overview: () => apiClient.get('/analytics/overview'),
  progress: () => apiClient.get('/analytics/progress'),
  bookAnalytics: (bookId: number) => apiClient.get(`/analytics/books/${bookId}`),
  weakest: () => apiClient.get('/analytics/weakest'),
  recentMistakes: () => apiClient.get('/analytics/recent-mistakes'),
  questionHistory: (questionId: number) => apiClient.get(`/analytics/questions/${questionId}/history`)
}

export const goalsAPI = {
  create: (data: any) => apiClient.post('/goals/', data),
  list: () => apiClient.get('/goals/'),
  get: (id: number) => apiClient.get(`/goals/${id}`),
  progress: (id: number) => apiClient.get(`/goals/${id}/progress`),
  generateTasks: (id: number) => apiClient.post(`/goals/${id}/generate-tasks`)
}

export const plannerAPI = {
  createTask: (data: any) => apiClient.post('/planner/tasks', data),
  listTasks: (params?: any) => apiClient.get('/planner/tasks', { params }),
  getTask: (id: number) => apiClient.get(`/planner/tasks/${id}`),
  updateTask: (id: number, data: any) => apiClient.patch(`/planner/tasks/${id}`, data),
  deleteTask: (id: number) => apiClient.delete(`/planner/tasks/${id}`),
  createPlacement: (data: any) => apiClient.post('/planner/placements', data),
  getWeek: (weekStart: string) => apiClient.get('/planner/week', { params: { week_start: weekStart } }),
  reorder: (data: any) => apiClient.post('/planner/reorder', data),
  suggestions: (weekStart?: string) => apiClient.get('/planner/suggestions', { params: { week_start: weekStart } }),
  catchup: (weekStart: string) => apiClient.get('/planner/catchup', { params: { week_start: weekStart } })
}

export const academicAPI = {
  schedules: {
    create: (data: any) => apiClient.post('/academic/schedules', data),
    list: (params?: any) => apiClient.get('/academic/schedules', { params }),
    update: (id: number, data: any) => apiClient.patch(`/academic/schedules/${id}`, data),
    delete: (id: number) => apiClient.delete(`/academic/schedules/${id}`)
  },
  classSessions: {
    create: (data: any) => apiClient.post('/academic/class-sessions', data),
    list: (params?: any) => apiClient.get('/academic/class-sessions', { params })
  },
  taughtLessons: {
    create: (data: any) => apiClient.post('/academic/taught-lessons', data),
    list: (params?: any) => apiClient.get('/academic/taught-lessons', { params })
  },
  homework: {
    create: (data: any) => apiClient.post('/academic/homework', data),
    list: (params?: any) => apiClient.get('/academic/homework', { params }),
    update: (id: number, data: any) => apiClient.patch(`/academic/homework/${id}`, data),
    delete: (id: number) => apiClient.delete(`/academic/homework/${id}`)
  },
  exams: {
    create: (data: any) => apiClient.post('/academic/exams', data),
    list: (params?: any) => apiClient.get('/academic/exams', { params }),
    get: (id: number) => apiClient.get(`/academic/exams/${id}`),
    delete: (id: number) => apiClient.delete(`/academic/exams/${id}`)
  }
}

export const socialAPI = {
  groups: {
    create: (data: any) => apiClient.post('/social/groups', data),
    list: () => apiClient.get('/social/groups'),
    join: (inviteCode: string) => apiClient.post('/social/groups/join', null, { params: { invite_code: inviteCode } }),
    members: (groupId: number) => apiClient.get(`/social/groups/${groupId}/members`)
  },
  sharing: {
    set: (data: any) => apiClient.post('/social/sharing', data),
    list: (groupId?: number) => apiClient.get('/social/sharing', { params: { group_id: groupId } })
  },
  compare: (data: any) => apiClient.post('/social/compare', data)
}

export const telegramAPI = {
  getConnection: () => apiClient.get('/telegram/connection'),
  createConnection: (data: any) => apiClient.post('/telegram/connection', data),
  verify: (code: string) => apiClient.post('/telegram/verify', { verification_code: code }),
  updatePrefs: (data: any) => apiClient.patch('/telegram/preferences', data),
  preview: (type: string) => apiClient.get(`/telegram/preview/${type}`),
  send: (type: string) => apiClient.post(`/telegram/send/${type}`)
}

export const dashboardAPI = {
  get: () => apiClient.get('/dashboard/')
}

export const reviewAPI = {
  list: (status: string = 'pending') => apiClient.get('/review/', { params: { status } }),
  due: () => apiClient.get('/review/due'),
  update: (id: number, status: string) => apiClient.post(`/review/${id}/update`, null, { params: { status } }),
  add: (questionId: number, bookId?: number, reason: string = 'manual') => apiClient.post('/review/add', null, { params: { question_id: questionId, book_id: bookId, reason } })
}

export const studentStateAPI = {
  get: () => apiClient.get('/student-state/')
}

export const progressAPI = {
  get: () => apiClient.get('/progress/'),
  overview: () => apiClient.get('/progress/overview')
}
