import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App shell', () => {
  it('shows the product name and the value proposition', () => {
    render(<App />)
    expect(screen.getByText('JoinPilot')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: /tested data model/i }),
    ).toBeInTheDocument()
  })
})
