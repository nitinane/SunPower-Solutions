import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { router } from './routes'
import './styles.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: (count, error) => count < 1 && !(error instanceof Error && 'status' in error && (error.status === 401 || error.status === 403)) }, mutations: { retry: 0 } } })
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider></React.StrictMode>)
