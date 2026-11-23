import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CodeBlock from './CodeBlock'

// Lessons mix Arabic prose with English terms and code, so each block picks
// its own direction from its first strong character.
const auto = (Tag) =>
  function AutoDir({ node: _node, ...props }) {
    return <Tag dir="auto" {...props} />
  }

const COMPONENTS = {
  h1: auto('h1'),
  h2: auto('h2'),
  h3: auto('h3'),
  h4: auto('h4'),
  p: auto('p'),
  li: auto('li'),
  ul: auto('ul'),
  ol: auto('ol'),
  blockquote: auto('blockquote'),
  td: auto('td'),
  th: auto('th'),
  table: function Table({ node: _node, ...props }) {
    return (
      <div className="scrollbar-thin overflow-x-auto">
        <table {...props} />
      </div>
    )
  },
  // Fenced code renders through CodeBlock; react-markdown wraps it in <pre>.
  pre: function Pre({ children }) {
    return <>{children}</>
  },
  code: function Code({ node: _node, className, children, ...props }) {
    const match = /language-([\w+-]+)/.exec(className ?? '')
    const text = String(children ?? '')
    if (match || text.includes('\n')) {
      return <CodeBlock language={match?.[1] ?? ''} code={text} />
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    )
  },
}

export default function LessonContent({ markdown }) {
  return (
    <div className="lesson-prose">
      <Markdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {markdown}
      </Markdown>
    </div>
  )
}
