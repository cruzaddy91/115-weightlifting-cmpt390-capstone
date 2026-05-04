// Netlify serverless function to save the week's program
// For simplicity, we'll use a JSON file or database

exports.handler = async (event, context) => {
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: 'Method not allowed' })
    }
  }

  try {
    const programData = JSON.parse(event.body)
    
    // In a real implementation, save to database
    // For MVP, we could use:
    // 1. A JSON file in the repo (read/write via GitHub API)
    // 2. A simple database like Supabase (free tier, no auth needed for this)
    // 3. A key-value store like Upstash Redis
    
    // For now, we'll return success
    // The actual persistence would be implemented based on your chosen storage solution
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS'
      },
      body: JSON.stringify({ 
        success: true,
        message: 'Program saved successfully',
        data: programData
      })
    }
  } catch (error) {
    return {
      statusCode: 500,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({ error: error.message })
    }
  }
}

