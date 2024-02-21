function post_run_text(){
    document.getElementById("div_status").innerHTML = "Loading...";

    query = document.getElementById("ta_query").value
    query = JSON.parse(query)
    request_data = {"query": query};

    fetch("./run_chemical_disease_qa", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.text();
    })
    .then(function(response_data){
        document.getElementById("div_result").innerHTML = response_data;
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function post_query_json(){
    document.getElementById("div_status").innerHTML = "Loading...";

    query = document.getElementById("ta_query").value
    query = JSON.parse(query)
    request_data = {"query": query};

    fetch("./query_chemical_disease_qa", {method: "post", body: JSON.stringify(request_data)})
    .then(function(response){
        return response.json();
    })
    .then(function(response_data){
        text = "<pre><code>" + JSON.stringify(response_data, null, 4) + "</code></pre>";
        document.getElementById("div_result").innerHTML = text;
        document.getElementById("div_status").innerHTML = "Ready";
    })
}

function get_query_json(){
    query = document.getElementById("ta_query").value;
    query = encodeURIComponent(query)
    url = `./query_chemical_disease_qa?query=${query}`
    window.open(url, "_blank");
}

async function post_run_text_stream(){
    document.getElementById("div_status").innerHTML = "Loading...";
    document.getElementById("div_result").innerHTML = "";

    query = document.getElementById("ta_query").value;
    query = JSON.parse(query);
    request_data = {"query": query};

    const response = await fetch("./run_chemical_disease_qa", {method: "post", body: JSON.stringify(request_data)});
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();

    while(true){
      const {value, done} = await reader.read();
      if (done) break;
      document.getElementById("div_result").innerHTML += value;
    }
    document.getElementById("div_status").innerHTML = "Ready";
}
