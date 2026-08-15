import { ChatView } from "@/components/assistant/ChatView";

const Index = () => {
  return (
    <main className="h-screen w-full overflow-hidden">
      <h1 className="sr-only">AI SQL Assistant — Query your database in natural language</h1>
      <ChatView />
    </main>
  );
};

export default Index;
