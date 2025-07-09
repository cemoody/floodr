#![allow(non_local_definitions)]

use futures::future::join_all;
use futures::stream::{self, StreamExt};
use pyo3::prelude::*;
use reqwest::{Client, Method};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, OnceLock};
use std::time::{Duration, Instant};
use tokio::sync::{RwLock, Semaphore};

// Global client cache for reuse across calls
static GLOBAL_CLIENT: OnceLock<Arc<RwLock<Option<Arc<Client>>>>> = OnceLock::new();

// Global Tokio runtime for blocking operations
static TOKIO_RUNTIME: OnceLock<tokio::runtime::Runtime> = OnceLock::new();

fn get_runtime() -> &'static tokio::runtime::Runtime {
    TOKIO_RUNTIME.get_or_init(|| {
        tokio::runtime::Runtime::new().expect("Failed to create Tokio runtime")
    })
}



// Get or create a global client with optimized settings
async fn get_or_create_global_client(num_requests: usize, enable_compression: bool) -> Arc<Client> {
    let client_cache = GLOBAL_CLIENT.get_or_init(|| Arc::new(RwLock::new(None)));
    
    // Try to get existing client
    {
        let read_guard = client_cache.read().await;
        if let Some(client) = read_guard.as_ref() {
            return client.clone();
        }
    }
    
    // Create new client with dynamic pool size
    let mut write_guard = client_cache.write().await;
    
    // Check again in case another thread created it
    if let Some(client) = write_guard.as_ref() {
        return client.clone();
    }
    
    // Create optimized client
    let pool_size = num_requests.max(256).min(8192); // Increased max for large batches
    let mut builder = Client::builder()
        .pool_max_idle_per_host(pool_size)
        .pool_idle_timeout(Duration::from_secs(300))
        .timeout(Duration::from_secs(60))
        .connect_timeout(Duration::from_secs(5))
        .tcp_keepalive(Duration::from_secs(60))
        .tcp_nodelay(true)
        .user_agent("floodr/1.0");
    
    if !enable_compression {
        builder = builder.no_gzip().no_brotli().no_deflate();
    }
    
    let client = Arc::new(builder.build().expect("Failed to build client"));
    *write_guard = Some(client.clone());
    
    client
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct Request {
    #[pyo3(get, set)]
    pub url: String,
    #[pyo3(get, set)]
    pub method: String,
    #[pyo3(get, set)]
    pub headers: Option<HashMap<String, String>>,
    #[pyo3(get, set)]
    pub json: Option<String>,
    #[pyo3(get, set)]
    pub data: Option<Vec<u8>>,
    #[pyo3(get, set)]
    pub timeout: Option<f64>,
}

#[pymethods]
impl Request {
    #[new]
    #[pyo3(signature = (url, method=None, headers=None, json=None, data=None, timeout=None))]
    fn new(
        url: String,
        method: Option<String>,
        headers: Option<HashMap<String, String>>,
        json: Option<String>,
        data: Option<Vec<u8>>,
        timeout: Option<f64>,
    ) -> Self {
        Request {
            url,
            method: method.unwrap_or_else(|| "GET".to_string()),
            headers,
            json,
            data,
            timeout,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[pyclass]
pub struct Response {
    #[pyo3(get)]
    pub status_code: u16,
    #[pyo3(get)]
    pub headers: HashMap<String, String>,
    #[pyo3(get)]
    pub content: Vec<u8>,
    #[pyo3(get)]
    pub text: Option<String>,
    #[pyo3(get)]
    pub json: Option<String>,
    #[pyo3(get)]
    pub url: String,
    #[pyo3(get)]
    pub elapsed: f64,
    #[pyo3(get)]
    pub error: Option<String>,
}

#[pymethods]
impl Response {
    fn __repr__(&self) -> String {
        format!("<Response [{}]>", self.status_code)
    }

    fn __str__(&self) -> String {
        format!("Response(status_code={}, url={})", self.status_code, self.url)
    }

    #[getter]
    fn ok(&self) -> bool {
        self.status_code >= 200 && self.status_code < 300
    }

    fn raise_for_status(&self) -> PyResult<()> {
        if !self.ok() {
            Err(pyo3::exceptions::PyException::new_err(format!(
                "HTTP {} Error for url: {}",
                self.status_code, self.url
            )))
        } else {
            Ok(())
        }
    }
}

// Optimized method parsing with static dispatch
#[inline]
fn parse_method(method_str: &str) -> Method {
    match method_str.as_bytes() {
        b"GET" | b"get" => Method::GET,
        b"POST" | b"post" => Method::POST,
        b"PUT" | b"put" => Method::PUT,
        b"DELETE" | b"delete" => Method::DELETE,
        b"HEAD" | b"head" => Method::HEAD,
        b"OPTIONS" | b"options" => Method::OPTIONS,
        b"PATCH" | b"patch" => Method::PATCH,
        _ => Method::GET,
    }
}

async fn execute_request(client: Arc<Client>, request: Request) -> Response {
    let start = Instant::now();
    let url = request.url.clone();
    
    // Parse method with optimized function
    let method = parse_method(&request.method);
    
    // Build request
    let mut req_builder = client.request(method, &url);
    
    // Add headers with capacity hint
    if let Some(headers) = request.headers {
        req_builder = headers.into_iter().fold(req_builder, |builder, (key, value)| {
            builder.header(key, value)
        });
    }
    
    // Add body
    if let Some(json_data) = request.json {
        req_builder = req_builder
            .header("Content-Type", "application/json")
            .body(json_data);
    } else if let Some(data) = request.data {
        req_builder = req_builder.body(data);
    }
    
    // Set timeout
    if let Some(timeout_secs) = request.timeout {
        req_builder = req_builder.timeout(Duration::from_secs_f64(timeout_secs));
    }
    
    // Execute request
    match req_builder.send().await {
        Ok(resp) => {
            let status = resp.status();
            
            // Optimize header collection with capacity
            let headers: HashMap<String, String> = resp.headers()
                .iter()
                .map(|(k, v)| (k.to_string(), v.to_str().unwrap_or("").to_string()))
                .collect();
            
            match resp.bytes().await {
                Ok(bytes) => {
                    let content = bytes.to_vec();
                    let content_len = content.len();
                    
                    // Only convert to text if it's likely text content and not too large
                    let (text, json) = if content_len < 1_000_000 {
                        if let Ok(text_str) = String::from_utf8(content.clone()) {
                            let json_str = if content_len < 100_000 { // Only parse JSON for smaller responses
                                serde_json::from_str::<serde_json::Value>(&text_str)
                                    .ok()
                                    .map(|v| v.to_string())
                            } else {
                                None
                            };
                            (Some(text_str), json_str)
                        } else {
                            (None, None)
                        }
                    } else {
                        (None, None)
                    };
                    
                    Response {
                        status_code: status.as_u16(),
                        headers,
                        content,
                        text,
                        json,
                        url,
                        elapsed: start.elapsed().as_secs_f64(),
                        error: None,
                    }
                }
                Err(e) => Response {
                    status_code: status.as_u16(),
                    headers,
                    content: vec![],
                    text: None,
                    json: None,
                    url,
                    elapsed: start.elapsed().as_secs_f64(),
                    error: Some(format!("Failed to read response body: {}", e)),
                },
            }
        }
        Err(e) => Response {
            status_code: 0,
            headers: HashMap::new(),
            content: vec![],
            text: None,
            json: None,
            url,
            elapsed: start.elapsed().as_secs_f64(),
            error: Some(format!("Request failed: {}", e)),
        },
    }
}

// Execute requests with controlled concurrency using semaphore
async fn execute_requests_with_backpressure(
    client: Arc<Client>,
    requests: Vec<Request>,
    max_concurrent: usize,
) -> Vec<Response> {
    let semaphore = Arc::new(Semaphore::new(max_concurrent));
    let mut responses = Vec::with_capacity(requests.len());
    
    // Process requests as a stream with controlled concurrency
    let stream = stream::iter(requests.into_iter().enumerate())
        .map(|(index, request)| {
            let client = client.clone();
            let semaphore = semaphore.clone();
            async move {
                let _permit = semaphore.acquire().await.unwrap();
                let response = execute_request(client, request).await;
                (index, response)
            }
        })
        .buffer_unordered(max_concurrent);
    
    // Collect responses maintaining order
    let mut results: Vec<(usize, Response)> = stream.collect().await;
    results.sort_by_key(|(index, _)| *index);
    
    for (_, response) in results {
        responses.push(response);
    }
    
    responses
}

#[pyclass]
struct ParallelClient {
    client: Arc<Client>,
}

#[pymethods]
impl ParallelClient {
    #[new]
    #[pyo3(signature = (max_connections=None, timeout=60.0, enable_compression=false))]
    fn new(max_connections: Option<usize>, timeout: f64, enable_compression: bool) -> PyResult<Self> {
        let pool_size = max_connections.unwrap_or(2048);
        let mut builder = Client::builder()
            .pool_max_idle_per_host(pool_size)
            .pool_idle_timeout(Duration::from_secs(300))
            .timeout(Duration::from_secs_f64(timeout))
            .connect_timeout(Duration::from_secs(5))
            .tcp_keepalive(Duration::from_secs(60))
            .tcp_nodelay(true)
            .user_agent("floodr/1.0");
        
        if !enable_compression {
            builder = builder.no_gzip().no_brotli().no_deflate();
        }
        
        let client = builder.build()
            .map_err(|e| pyo3::exceptions::PyException::new_err(format!("Failed to create client: {}", e)))?;
        
        Ok(ParallelClient {
            client: Arc::new(client),
        })
    }

    fn execute<'py>(&self, py: Python<'py>, requests: Vec<Request>) -> PyResult<Bound<'py, PyAny>> {
        let client = self.client.clone();
        let num_requests = requests.len();
        
        // Block on the async operation and return the result directly
        let responses = py.allow_threads(|| {
            get_runtime().block_on(async move {
                if num_requests > 100 {
                    let max_concurrent = (num_requests / 10).max(100).min(500);
                    execute_requests_with_backpressure(client, requests, max_concurrent).await
                } else {
                    let futures: Vec<_> = requests
                        .into_iter()
                        .map(|req| {
                            let client = client.clone();
                            execute_request(client, req)
                        })
                        .collect();
                    
                    join_all(futures).await
                }
            })
        });
        
        Ok(responses.into_pyobject(py)?.into_any())
    }
    
    // Execute with custom concurrency limit
    fn execute_with_concurrency<'py>(&self, py: Python<'py>, requests: Vec<Request>, max_concurrent: Option<usize>) -> PyResult<Bound<'py, PyAny>> {
        let client = self.client.clone();
        let num_requests = requests.len();
        
        let responses = py.allow_threads(|| {
            get_runtime().block_on(async move {
                if let Some(limit) = max_concurrent {
                    // Use specified concurrency limit
                    execute_requests_with_backpressure(client, requests, limit).await
                } else {
                    // Use default behavior
                    if num_requests > 100 {
                        let max_concurrent = (num_requests / 10).max(100).min(500);
                        execute_requests_with_backpressure(client, requests, max_concurrent).await
                    } else {
                        // For smaller batches, use the original approach
                        let futures: Vec<_> = requests
                            .into_iter()
                            .map(|req| {
                                let client = client.clone();
                                execute_request(client, req)
                            })
                            .collect();
                        
                        join_all(futures).await
                    }
                }
            })
        });
        
        Ok(responses.into_pyobject(py)?.into_any())
    }
    
    // Warm up the connection pool by making multiple concurrent requests
    #[pyo3(signature = (url, num_connections=10))]
    fn warmup<'py>(&self, py: Python<'py>, url: String, num_connections: Option<usize>) -> PyResult<Bound<'py, PyAny>> {
        let client = self.client.clone();
        let connections_to_warm = num_connections.unwrap_or(10);
        
        py.allow_threads(|| {
            get_runtime().block_on(async move {
                // Create multiple HEAD requests to warm up connections
                let warmup_futures: Vec<_> = (0..connections_to_warm)
                    .map(|_| {
                        let client = client.clone();
                        let url = url.clone();
                        async move {
                            let _ = client
                                .head(&url)
                                .timeout(Duration::from_secs(5))
                                .send()
                                .await;
                        }
                    })
                    .collect();
                
                // Execute all warmup requests concurrently
                join_all(warmup_futures).await;
            })
        });
        
        Ok(py.None().into_bound(py))
    }
}

/// Fast parallel HTTP client for Python, powered by Rust
#[pymodule]
fn floodr(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Request>()?;
    m.add_class::<Response>()?;
    m.add_class::<ParallelClient>()?;
    
    // Add module-level execute function with optimizations
    // This is the synchronous version that will be wrapped in Python
    #[pyfunction]
    #[pyo3(signature = (requests, max_connections=None, timeout=60.0, enable_compression=false, use_global_client=true, max_concurrent=None))]
    fn execute_sync<'py>(
        py: Python<'py>,
        requests: Vec<Request>,
        max_connections: Option<usize>,
        timeout: f64,
        enable_compression: bool,
        use_global_client: bool,
        max_concurrent: Option<usize>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let num_requests = requests.len();
        
        let responses = py.allow_threads(|| {
            get_runtime().block_on(async move {
                let client = if use_global_client {
                    // Use global client with dynamic pool sizing
                    get_or_create_global_client(num_requests, enable_compression).await
                } else {
                    // Create a new client with custom settings
                    let pool_size = max_connections.unwrap_or_else(|| num_requests.max(256).min(8192));
                    let mut builder = Client::builder()
                        .pool_max_idle_per_host(pool_size)
                        .pool_idle_timeout(Duration::from_secs(300))
                        .timeout(Duration::from_secs_f64(timeout))
                        .connect_timeout(Duration::from_secs(5))
                        .tcp_keepalive(Duration::from_secs(60))
                        .tcp_nodelay(true)
                        .user_agent("floodr/1.0");
                    
                    if !enable_compression {
                        builder = builder.no_gzip().no_brotli().no_deflate();
                    }
                    
                    Arc::new(builder.build().expect("Failed to build client"))
                };
                
                // Use specified concurrency or default behavior
                if let Some(limit) = max_concurrent {
                    execute_requests_with_backpressure(client, requests, limit).await
                } else {
                    // Use default behavior based on batch size
                    if num_requests > 100 {
                        let max_concurrent = (num_requests / 10).max(100).min(500);
                        execute_requests_with_backpressure(client, requests, max_concurrent).await
                    } else {
                        // For smaller batches, use the original approach
                        let futures: Vec<_> = requests
                            .into_iter()
                            .map(|req| {
                                let client = client.clone();
                                execute_request(client, req)
                            })
                            .collect();
                        
                        join_all(futures).await
                    }
                }
            })
        });
        
        Ok(responses.into_pyobject(py)?.into_any())
    }
    
    // Warmup function for global client - synchronous version
    #[pyfunction]
    #[pyo3(signature = (url, num_connections=10, enable_compression=false))]
    fn warmup_sync<'py>(py: Python<'py>, url: String, num_connections: Option<usize>, enable_compression: Option<bool>) -> PyResult<Bound<'py, PyAny>> {
        let connections_to_warm = num_connections.unwrap_or(10);
        let compression = enable_compression.unwrap_or(false);
        
        py.allow_threads(|| {
            get_runtime().block_on(async move {
                // Get or create the global client with appropriate pool size
                let client = get_or_create_global_client(connections_to_warm, compression).await;
                
                // Create multiple lightweight HEAD requests to the same domain
                let warmup_futures: Vec<_> = (0..connections_to_warm)
                    .map(|_| {
                        let client = client.clone();
                        let url = url.clone();
                        async move {
                            // Use HEAD request with short timeout for warming up
                            let _ = client
                                .head(&url)
                                .timeout(Duration::from_secs(5))
                                .send()
                                .await;
                        }
                    })
                    .collect();
                
                // Execute all warmup requests concurrently
                join_all(warmup_futures).await;
            })
        });
        
        Ok(py.None().into_bound(py))
    }
    
    // Advanced warmup with custom paths for better connection reuse
    #[pyfunction]
    #[pyo3(signature = (base_url, paths=None, num_connections=None, enable_compression=None, method=None))]
    fn warmup_advanced_sync<'py>(
        py: Python<'py>, 
        base_url: String, 
        paths: Option<Vec<String>>,
        num_connections: Option<usize>,
        enable_compression: Option<bool>,
        method: Option<String>
    ) -> PyResult<Bound<'py, PyAny>> {
        let connections_to_warm = num_connections.unwrap_or(10);
        let compression = enable_compression.unwrap_or(false);
        let request_method = method.unwrap_or_else(|| "HEAD".to_string());
        
        let results = py.allow_threads(|| {
            get_runtime().block_on(async move {
            // Get or create the global client
            let client = get_or_create_global_client(connections_to_warm, compression).await;
            
            // Use provided paths or default to root
            let paths = paths.unwrap_or_else(|| vec!["/".to_string()]);
            
            // Create warmup requests
            let warmup_futures: Vec<_> = (0..connections_to_warm)
                .map(|i| {
                    let client = client.clone();
                    let base_url = base_url.clone();
                    let path = paths[i % paths.len()].clone();
                    let method = request_method.clone();
                    
                    async move {
                        let full_url = if path.starts_with('/') {
                            format!("{}{}", base_url.trim_end_matches('/'), path)
                        } else {
                            format!("{}/{}", base_url.trim_end_matches('/'), path)
                        };
                        
                        let req_method = parse_method(&method);
                        let start = Instant::now();
                        
                        let result = client
                            .request(req_method, &full_url)
                            .timeout(Duration::from_secs(5))
                            .send()
                            .await;
                        
                        let elapsed = start.elapsed().as_secs_f64();
                        
                        match result {
                            Ok(resp) => (full_url, resp.status().as_u16(), elapsed, None),
                            Err(e) => (full_url, 0, elapsed, Some(e.to_string())),
                        }
                    }
                })
                .collect();
            
                // Execute all warmup requests and collect results
                join_all(warmup_futures).await
            })
        });
        
        // Convert results to Python dict
        let py_results: Vec<HashMap<&str, PyObject>> = results
            .into_iter()
            .map(|(url, status, elapsed, error)| {
                let mut result = HashMap::new();
                result.insert("url", url.into_pyobject(py).unwrap().into());
                result.insert("status", status.into_pyobject(py).unwrap().into());
                result.insert("elapsed", elapsed.into_pyobject(py).unwrap().into());
                if let Some(err) = error {
                    result.insert("error", err.into_pyobject(py).unwrap().into());
                }
                result
            })
            .collect();
        
        Ok(py_results.into_pyobject(py)?.into_any())
    }
    
    m.add_function(wrap_pyfunction!(execute_sync, m)?)?;
    m.add_function(wrap_pyfunction!(warmup_sync, m)?)?;
    m.add_function(wrap_pyfunction!(warmup_advanced_sync, m)?)?;
    
    Ok(())
}



#[cfg(test)]
mod tests {
    use super::*;
    use tokio::runtime::Runtime;

    #[test]
    fn test_parse_method() {
        assert!(matches!(parse_method("GET"), Method::GET));
        assert!(matches!(parse_method("get"), Method::GET));
        assert!(matches!(parse_method("POST"), Method::POST));
        assert!(matches!(parse_method("post"), Method::POST));
        assert!(matches!(parse_method("PUT"), Method::PUT));
        assert!(matches!(parse_method("DELETE"), Method::DELETE));
        assert!(matches!(parse_method("HEAD"), Method::HEAD));
        assert!(matches!(parse_method("OPTIONS"), Method::OPTIONS));
        assert!(matches!(parse_method("PATCH"), Method::PATCH));
        assert!(matches!(parse_method("unknown"), Method::GET)); // Default
    }

    #[test]
    fn test_request_creation() {
        let req = Request::new(
            "https://example.com".to_string(),
            Some("POST".to_string()),
            Some(HashMap::new()),
            Some("{\"key\": \"value\"}".to_string()),
            None,
            Some(30.0),
        );
        
        assert_eq!(req.url, "https://example.com");
        assert_eq!(req.method, "POST");
        assert!(req.headers.is_some());
        assert!(req.json.is_some());
        assert!(req.data.is_none());
        assert_eq!(req.timeout, Some(30.0));
    }

    #[test]
    fn test_response_ok() {
        let resp = Response {
            status_code: 200,
            headers: HashMap::new(),
            content: vec![],
            text: None,
            json: None,
            url: "https://example.com".to_string(),
            elapsed: 1.0,
            error: None,
        };
        
        assert!(resp.ok());
        
        let resp_404 = Response {
            status_code: 404,
            headers: HashMap::new(),
            content: vec![],
            text: None,
            json: None,
            url: "https://example.com".to_string(),
            elapsed: 1.0,
            error: None,
        };
        
        assert!(!resp_404.ok());
    }

    #[test]
    #[ignore = "requires network access"]
    fn test_execute_request_success() {
        let rt = Runtime::new().unwrap();
        
        rt.block_on(async {
            let client = Arc::new(Client::new());
            let req = Request::new(
                "https://httpbin.org/json".to_string(),
                None,
                None,
                None,
                None,
                Some(10.0),
            );
            
            let resp = execute_request(client, req).await;
            
            assert_eq!(resp.status_code, 200);
            assert!(resp.error.is_none());
            assert!(!resp.content.is_empty());
            assert!(resp.text.is_some());
            assert!(resp.json.is_some());
        });
    }

    #[test]
    #[ignore = "requires network access"]
    fn test_execute_request_timeout() {
        let rt = Runtime::new().unwrap();
        
        rt.block_on(async {
            let client = Arc::new(Client::new());
            let req = Request::new(
                "https://httpbin.org/delay/5".to_string(),
                None,
                None,
                None,
                None,
                Some(0.1), // Very short timeout
            );
            
            let resp = execute_request(client, req).await;
            
            assert_eq!(resp.status_code, 0);
            assert!(resp.error.is_some());
            assert!(resp.elapsed < 1.0); // Should fail quickly
        });
    }

    #[test]
    fn test_execute_request_invalid_domain() {
        let rt = Runtime::new().unwrap();
        
        rt.block_on(async {
            let client = Arc::new(Client::new());
            let req = Request::new(
                "https://invalid-domain-that-does-not-exist-xyz.com".to_string(),
                None,
                None,
                None,
                None,
                Some(2.0),
            );
            
            let resp = execute_request(client, req).await;
            
            assert_eq!(resp.status_code, 0);
            assert!(resp.error.is_some());
            assert!(resp.error.unwrap().contains("Request failed"));
        });
    }

    #[test]
    #[ignore = "requires network access"]
    fn test_concurrent_requests() {
        let rt = Runtime::new().unwrap();
        
        rt.block_on(async {
            let client = Arc::new(Client::new());
            let requests: Vec<Request> = (0..5)
                .map(|i| Request::new(
                    format!("https://httpbin.org/status/{}", 200 + i),
                    None,
                    None,
                    None,
                    None,
                    Some(10.0),
                ))
                .collect();
            
            let responses = execute_requests_with_backpressure(client, requests, 3).await;
            
            assert_eq!(responses.len(), 5);
            for (i, resp) in responses.iter().enumerate() {
                assert_eq!(resp.status_code, 200 + i as u16);
                assert!(resp.error.is_none());
            }
        });
    }

    #[test]
    #[ignore = "requires network access"]
    fn test_json_request() {
        let rt = Runtime::new().unwrap();
        
        rt.block_on(async {
            let client = Arc::new(Client::new());
            let req = Request::new(
                "https://httpbin.org/post".to_string(),
                Some("POST".to_string()),
                None,
                Some("{\"test\": \"data\"}".to_string()),
                None,
                Some(10.0),
            );
            
            let resp = execute_request(client, req).await;
            
            assert_eq!(resp.status_code, 200);
            assert!(resp.error.is_none());
            assert!(resp.json.is_some());
            
            // httpbin echoes back the JSON we sent
            let json_str = resp.json.unwrap();
            assert!(json_str.contains("\"test\""));
            assert!(json_str.contains("\"data\""));
        });
    }

    #[test]
    #[ignore = "requires network access"]
    fn test_headers() {
        let rt = Runtime::new().unwrap();
        
        rt.block_on(async {
            let client = Arc::new(Client::new());
            let mut headers = HashMap::new();
            headers.insert("X-Test-Header".to_string(), "test-value".to_string());
            
            let req = Request::new(
                "https://httpbin.org/headers".to_string(),
                None,
                Some(headers),
                None,
                None,
                Some(10.0),
            );
            
            let resp = execute_request(client, req).await;
            
            assert_eq!(resp.status_code, 200);
            assert!(resp.error.is_none());
            
            // httpbin returns the headers we sent
            let text = resp.text.unwrap();
            assert!(text.contains("X-Test-Header"));
            assert!(text.contains("test-value"));
        });
    }

    #[test]
    fn test_global_client() {
        let rt = Runtime::new().unwrap();
        
        rt.block_on(async {
            // Get global client twice - should be the same instance
            let client1 = get_or_create_global_client(100, false).await;
            let client2 = get_or_create_global_client(100, false).await;
            
            // Both should be the same Arc pointer
            assert!(Arc::ptr_eq(&client1, &client2));
        });
    }
} 