import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import './components/AppLayout.css';
import HomeScreen from './screens/HomeScreen';
import ProfileScreen from './screens/ProfileScreen';
import SuggestionScreen from './screens/SuggestionScreen';
import HistoryScreen from './screens/HistoryScreen';
import AllRecipesScreen from './screens/AllRecipesScreen';
import RecipeFormScreen from './screens/RecipeFormScreen';

function App() {
  return (
    <Router>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomeScreen />} />
          <Route path="/recipes" element={<AllRecipesScreen />} />
          <Route path="/recipes/new" element={<RecipeFormScreen />} />
          <Route path="/recipes/custom/:recipeId/edit" element={<RecipeFormScreen />} />
          <Route path="/profile/:profileId" element={<ProfileScreen />} />
          <Route path="/profile/:profileId/suggest" element={<SuggestionScreen />} />
          <Route path="/profile/:profileId/history" element={<HistoryScreen />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
