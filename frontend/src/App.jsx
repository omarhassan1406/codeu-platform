import { useCallback, useState } from 'react'
import Classroom from './components/Classroom'
import Header from './components/Header'
import GenerationProgress from './components/onboarding/GenerationProgress'
import OnboardingFlow from './components/onboarding/OnboardingFlow'
import SuggestionsView from './components/onboarding/SuggestionsView'
import { api } from './lib/api'
import { loadJSON, saveJSON } from './lib/storage'

// Views: onboarding (questions) -> suggestions -> generating | classroom.
// Returning learners with a saved profile land straight in the classroom.
export default function App() {
  const [profile, setProfile] = useState(() => loadJSON('profile'))
  const [view, setView] = useState(() => (loadJSON('profile') ? 'classroom' : 'onboarding'))
  const [suggestions, setSuggestions] = useState(null)
  const [suggestError, setSuggestError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [courseId, setCourseId] = useState(() => loadJSON('course'))
  const [job, setJob] = useState(() => loadJSON('job'))
  const [generateError, setGenerateError] = useState(null)
  const [generating, setGenerating] = useState(false)

  const fetchSuggestions = async (nextProfile) => {
    setSubmitting(true)
    setSuggestError(null)
    try {
      const result = await api.suggest(nextProfile)
      setSuggestions(result.suggestions)
      setProfile(nextProfile)
      saveJSON('profile', nextProfile)
      setView('suggestions')
    } catch (error) {
      setSuggestError(error.message)
    } finally {
      setSubmitting(false)
    }
  }

  const changeCourse = useCallback((id) => {
    setCourseId(id)
    saveJSON('course', id)
  }, [])

  const openCourse = (id) => {
    changeCourse(id)
    setView('classroom')
  }

  const generate = async (topic) => {
    setGenerating(true)
    setGenerateError(null)
    try {
      const result = await api.generateCourse(topic)
      const nextJob = { jobId: result.job_id, topic: result.course_topic }
      setJob(nextJob)
      saveJSON('job', nextJob)
      setView('generating')
    } catch (error) {
      setGenerateError(error.message)
    } finally {
      setGenerating(false)
    }
  }

  const navigate = (target) => {
    if (target === 'suggestions' && (!suggestions || !profile)) {
      if (profile) fetchSuggestions(profile)
      else setView('onboarding')
      return
    }
    setView(target)
  }

  const leaveGeneration = (finished) => {
    if (finished) {
      setJob(null)
      saveJSON('job', null)
    }
  }

  if (view === 'onboarding') {
    return (
      <OnboardingFlow
        initialProfile={profile}
        onSubmit={fetchSuggestions}
        onSkip={profile ? () => setView('classroom') : undefined}
        submitting={submitting}
        error={suggestError}
      />
    )
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header view={view} onNavigate={navigate} pendingJob={job} onOpenJob={() => setView('generating')} />

      {view === 'suggestions' && suggestions && (
        <SuggestionsView
          suggestions={suggestions}
          onOpen={openCourse}
          onGenerate={generate}
          onEditProfile={() => setView('onboarding')}
          generateError={generateError}
          busy={generating}
        />
      )}

      {view === 'generating' && job && (
        <GenerationProgress
          key={job.jobId}
          jobId={job.jobId}
          topic={job.topic}
          onOpen={(id) => {
            leaveGeneration(true)
            openCourse(id)
          }}
          onBack={(finished) => {
            leaveGeneration(finished)
            navigate('suggestions')
          }}
        />
      )}

      {view === 'classroom' && (
        <Classroom courseId={courseId} onCourseChange={changeCourse} onFindCourses={() => navigate('suggestions')} />
      )}
    </div>
  )
}
