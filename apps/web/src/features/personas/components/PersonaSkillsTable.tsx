// PersonaSkillsTable — read-only Darstellung der Persona-Skills als Tabelle
// (Track F). Spiegelt die Agenten-Sicht: `get_persona` haengt dieselbe
// Skill-Tabelle (Skill | Hinweis) an den gerenderten Profil-Body. Auf der
// Detail-Page macht das fuer den Operator sichtbar, wie der Agent die Skills
// gebrieft bekommt — ohne sie hier editieren zu muessen (das macht der
// PersonaSkillsEditor im Formular).

import type { SkillRef } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

interface PersonaSkillsTableProps {
  skills: SkillRef[]
}

export function PersonaSkillsTable({ skills }: PersonaSkillsTableProps) {
  const named = skills.filter((skill) => skill.name.trim() !== '')
  if (named.length === 0) {
    return null
  }
  return (
    <Card data-testid="persona-skills-table">
      <CardHeader>
        <CardTitle>Skills (Agenten-Sicht)</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-1/3">Skill</TableHead>
              <TableHead>Hinweis</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {named.map((skill, index) => (
              <TableRow key={`${skill.name}-${index}`}>
                <TableCell className="font-medium">{skill.name}</TableCell>
                <TableCell className="text-muted-foreground">
                  {skill.note.trim() !== '' ? skill.note : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
