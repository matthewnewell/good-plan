const KEY = 'good-plan:person-id'

/** The person who launched this app from Conway's Depot (`?person_id=`), remembered for the tab's
 * session since the param vanishes on the first in-app navigation. Only used to author Journal
 * notes; Good Plan has no login and no persona switcher of its own. */
export function readPersonId(): string | undefined {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get('person_id')
    if (fromUrl) {
      window.sessionStorage.setItem(KEY, fromUrl)
      return fromUrl
    }
    return window.sessionStorage.getItem(KEY) ?? undefined
  } catch {
    return undefined
  }
}
