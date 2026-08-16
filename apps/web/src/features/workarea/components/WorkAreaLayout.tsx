import { Outlet } from 'react-router-dom'

import { Container } from '@/components/layout/Container'

import { WorkAreaNav } from './WorkAreaNav'

// Layout-Wrapper aller Arbeitsbereichs-Routen (Muster `SettingsLayout`):
// rendert die Sub-Navigation einmal, die Page kommt uebers Outlet. Die Pages
// bringen ihren eigenen `Container`/`PageHeader` mit — der aeussere Container
// hier traegt nur die Nav.
export function WorkAreaLayout() {
  return (
    <>
      <Container className="pb-0">
        <WorkAreaNav />
      </Container>
      <Outlet />
    </>
  )
}
