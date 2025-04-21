// frontend/src/components/SearchBar.jsx
import React from 'react';
import './SearchBar.css'; // Keep its own CSS for layout structure

// Accept inputClassName and buttonClassName as props
function SearchBar({
  searchTerm,
  onSearchChange,
  onSearchSubmit,
  placeholder,
  inputClassName = '', // Default to empty string
  buttonClassName = ''  // Default to empty string
}) {

  // Handle input change
  const handleChange = (event) => {
    if (onSearchChange) {
      onSearchChange(event); // Pass the event up
    }
  };

  // Handle Enter key press
   const handleKeyDown = (event) => {
     if (event.key === 'Enter' && onSearchSubmit) {
       onSearchSubmit();
     }
   };

  return (
    // Container for layout (e.g., side-by-side) defined in SearchBar.css
    <div className="search-bar-container">
      <input
        type="search" // Use type="search" for potential browser features like clear button
        placeholder={placeholder || "Search..."}
        value={searchTerm}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        // Apply base class AND passed className prop
        className={`search-input ${inputClassName}`}
      />
      <button
        onClick={onSearchSubmit}
        // Apply base class AND passed className prop
        className={`search-button ${buttonClassName}`}
      >
        Search
      </button>
    </div>
  );
}

export default SearchBar;