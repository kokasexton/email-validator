import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { SingleValidate } from './pages/SingleValidate';
import { BulkValidate } from './pages/BulkValidate';
import { History } from './pages/History';
import { ApiDocs } from './pages/ApiDocs';
import './App.css';

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/single" element={<SingleValidate />} />
          <Route path="/bulk" element={<BulkValidate />} />
          <Route path="/history" element={<History />} />
          <Route path="/history/:jobId" element={<History />} />
          <Route path="/api-docs" element={<ApiDocs />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
