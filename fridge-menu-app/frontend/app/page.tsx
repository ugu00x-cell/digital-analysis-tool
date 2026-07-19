import IngredientForm from '@/components/IngredientForm'

export default function Home() {
  return (
    <div className="flex min-h-screen justify-center bg-zinc-50 px-4 py-10 font-sans">
      <main className="flex w-full max-w-2xl justify-center">
        <IngredientForm />
      </main>
    </div>
  )
}
