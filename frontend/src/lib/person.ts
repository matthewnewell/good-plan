import { currentPersonId } from '@conways/drawer'

/** Who's using the app: the ecosystem's "viewing as" persona (the header's user menu, a Depot link's
 * `?person_id=`). The app reloads when it changes (PersonaProvider reloadOnSwitch in main.tsx), so
 * reading it once per page is enough. */
export function readPersonId(): string | undefined {
  return currentPersonId() ?? undefined
}
