// The pipeline saves each lesson with a "# section / ## step" header the
// sidebar already shows; drop it so the stage opens on the lesson itself.
export function stripSavedHeader(markdown, sectionTitle, stepTitle) {
  const text = markdown.replace(/\r\n/g, '\n')
  const header = `# ${sectionTitle}\n## ${stepTitle}\n\n`
  return text.startsWith(header) ? text.slice(header.length) : text
}
