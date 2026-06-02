import { Outlet } from 'react-router-dom'

import { Container } from '@/components/layout/Container'

import { SettingsNav } from './SettingsNav'

// Layout-Wrapper für alle Settings-Routen: rendert die Space-Sub-Navigation
// einmal und gibt die jeweilige Page über das Outlet aus. Die Pages bringen
// ihren eigenen `Container`/`PageHeader` mit — der äußere `Container` hier
// trägt nur die Nav, damit Bestands-Pages (Mitglieder, API-Tokens) unverändert
// bleiben.
export function SettingsLayout() {
  return (
    <>
      <Container className="pb-0">
        <SettingsNav />
      </Container>
      <Outlet />
    </>
  )
}
