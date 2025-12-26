import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from '@/components/layout';
import { Dashboard, RoundAnalysis, ValueBets, Combinations, AIInsights, Settings } from '@/pages';
import MatchAnalysis from '@/pages/MatchAnalysis';
import '@/styles/globals.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/match/:id" element={<MatchAnalysis />} />
            <Route path="/rounds" element={<RoundAnalysis />} />
            <Route path="/value-bets" element={<ValueBets />} />
            <Route path="/combinations" element={<Combinations />} />
            <Route path="/ai-insights" element={<AIInsights />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
