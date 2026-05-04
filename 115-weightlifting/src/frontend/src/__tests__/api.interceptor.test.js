import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'

import { apiClient, getProgramsFromBackend } from '../services/api'
import {
  getToken,
  setCurrentUser,
  setToken,
} from '../utils/auth'

const installAdapter = (handlerFn) => {
  const original = apiClient.defaults.adapter
  apiClient.defaults.adapter = handlerFn
  return () => {
    apiClient.defaults.adapter = original
  }
}

describe('apiClient 401 interceptor', () => {
  let restoreAdapter

  beforeEach(() => {
    setToken('initial-access')
    setCurrentUser({ username: 'u', user_type: 'athlete' })
  })

  afterEach(() => {
    if (restoreAdapter) restoreAdapter()
    restoreAdapter = null
  })

  it('refreshes on 401 and retries the original request', async () => {
    const postSpy = vi.spyOn(axios, 'post').mockResolvedValue({
      data: { access: 'new-access', refresh: 'rotated-refresh' },
    })

    let callCount = 0
    restoreAdapter = installAdapter(async (config) => {
      callCount += 1
      if (callCount === 1) {
        return Promise.reject({
          response: { status: 401, data: {} },
          config,
        })
      }
      expect(config.headers.Authorization).toBe('Bearer new-access')
      return {
        data: [{ id: 1, name: 'Program' }],
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    })

    const result = await getProgramsFromBackend()
    expect(result).toEqual([{ id: 1, name: 'Program' }])
    expect(postSpy).toHaveBeenCalledOnce()
    expect(postSpy.mock.calls[0][0]).toMatch(/token\/refresh\/$/)
    expect(postSpy.mock.calls[0][1]).toEqual({})
    expect(postSpy.mock.calls[0][2]).toMatchObject({ withCredentials: true })
    expect(getToken()).toBe('new-access')
    expect(callCount).toBe(2)
  })

  it('clears auth and redirects on failed refresh', async () => {
    vi.spyOn(axios, 'post').mockRejectedValue({
      response: { status: 401, data: {} },
    })
    const assign = vi.fn()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { pathname: '/athlete', assign },
    })

    restoreAdapter = installAdapter(async (config) =>
      Promise.reject({ response: { status: 401, data: {} }, config })
    )

    await expect(getProgramsFromBackend()).rejects.toBeTruthy()
    expect(getToken()).toBeNull()
    expect(assign).toHaveBeenCalledWith('/login')
  })

  it('does not loop refresh when the refresh endpoint itself 401s', async () => {
    vi.spyOn(axios, 'post').mockRejectedValue({
      response: { status: 401, data: {} },
    })
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { pathname: '/login', assign: vi.fn() },
    })

    let callCount = 0
    restoreAdapter = installAdapter(async (config) => {
      callCount += 1
      return Promise.reject({ response: { status: 401, data: {} }, config })
    })

    await expect(getProgramsFromBackend()).rejects.toBeTruthy()
    expect(callCount).toBe(1)
  })

  it('coalesces concurrent 401s into a single refresh call', async () => {
    const postSpy = vi.spyOn(axios, 'post').mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(() => resolve({ data: { access: 'new-access' } }), 10)
        )
    )

    let call = 0
    restoreAdapter = installAdapter(async (config) => {
      call += 1
      if (!config.headers?.Authorization?.includes('new-access')) {
        return Promise.reject({ response: { status: 401, data: {} }, config })
      }
      return {
        data: { ok: true, hit: call },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    })

    const [a, b, c] = await Promise.all([
      apiClient.get('/api/a/'),
      apiClient.get('/api/b/'),
      apiClient.get('/api/c/'),
    ])
    expect(a.data.ok).toBe(true)
    expect(b.data.ok).toBe(true)
    expect(c.data.ok).toBe(true)
    expect(postSpy).toHaveBeenCalledOnce()
  })
})
