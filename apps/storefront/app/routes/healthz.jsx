// Liveness endpoint for the storefront container's healthcheck.
//
// Deliberately independent of the API and of any redirect. The healthcheck used
// to request "/", which redirects to /stores and there loads the public store
// directory from the API - so an API blip marked the container unhealthy. That
// matters far beyond this service: `front` (nginx) depends on the storefront
// being healthy, so an unhealthy storefront stops nginx from starting at all,
// which takes the entire origin down (chmaba.com, admin.chmaba.com and /api/v1
// included) rather than just shops.chmaba.com.
//
// This answers "is the Node server up", which is the only thing a container
// healthcheck can honestly judge.
export function loader() {
  return new Response("ok\n", {
    status: 200,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
