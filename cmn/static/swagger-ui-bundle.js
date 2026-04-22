/*
 * 폐쇄망 환경에서도 /docs 화면이 비지 않도록 만드는 경량 Swagger 문서 렌더러입니다.
 * FastAPI의 get_swagger_ui_html()가 호출하는 SwaggerUIBundle(...) 형태를 그대로 맞춰
 * 기존 Python 라우트 코드를 바꾸지 않고도 OpenAPI 문서를 읽어 화면에 표시합니다.
 */
(function () {
  "use strict";

  // HTTP 메서드별 강조 색상입니다.
  var METHOD_COLORS = {
    GET: "#1f7a4f",
    POST: "#0f62fe",
    PUT: "#7a3ff2",
    PATCH: "#b36a00",
    DELETE: "#b42318",
    OPTIONS: "#475467",
    HEAD: "#6941c6",
  };

  function escapeHtml(value) {
    // 문자열을 HTML에 그대로 넣어도 안전하도록 특수문자를 치환합니다.
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function asArray(value) {
    // OpenAPI 필드가 배열이 아닐 수도 있으므로 항상 배열로 정규화합니다.
    return Array.isArray(value) ? value : [];
  }

  function getMethodColor(method) {
    return METHOD_COLORS[method] || "#475467";
  }

  function formatJson(value) {
    // 객체/배열은 보기 좋게 들여쓰기하여 예시 블록에 표시합니다.
    if (value == null) {
      return "";
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch (error) {
      return String(value);
    }
  }

  function resolveSchemaName(schema) {
    // $ref가 있으면 마지막 경로 조각을 타입 이름처럼 보여줍니다.
    if (!schema) {
      return "Unknown";
    }

    if (schema.$ref) {
      return schema.$ref.split("/").pop() || schema.$ref;
    }

    if (schema.type) {
      return schema.type;
    }

    if (schema.anyOf) {
      return asArray(schema.anyOf).map(resolveSchemaName).join(" | ");
    }

    if (schema.oneOf) {
      return asArray(schema.oneOf).map(resolveSchemaName).join(" | ");
    }

    if (schema.allOf) {
      return asArray(schema.allOf).map(resolveSchemaName).join(" & ");
    }

    return "object";
  }

  function renderServers(spec) {
    var servers = asArray(spec.servers);

    if (!servers.length) {
      return "<p class=\"swagger-empty\">서버 정보가 정의되어 있지 않습니다.</p>";
    }

    return (
      "<ul class=\"swagger-server-list\">" +
      servers
        .map(function (server) {
          return (
            "<li>" +
            "<code>" + escapeHtml(server.url || "") + "</code>" +
            (server.description
              ? "<p>" + escapeHtml(server.description) + "</p>"
              : "") +
            "</li>"
          );
        })
        .join("") +
      "</ul>"
    );
  }

  function renderParameterList(parameters) {
    var items = asArray(parameters);

    if (!items.length) {
      return "<p class=\"swagger-empty\">파라미터가 없습니다.</p>";
    }

    return (
      "<div class=\"swagger-grid\">" +
      items
        .map(function (parameter) {
          var schemaName = resolveSchemaName(parameter.schema);
          return (
            "<div class=\"swagger-kv-card\">" +
            "<div class=\"swagger-kv-head\">" +
            "<strong>" + escapeHtml(parameter.name || "") + "</strong>" +
            "<span>" + escapeHtml(parameter["in"] || "") + "</span>" +
            "</div>" +
            "<p>타입: <code>" + escapeHtml(schemaName) + "</code></p>" +
            "<p>필수 여부: <code>" +
            escapeHtml(parameter.required ? "required" : "optional") +
            "</code></p>" +
            (parameter.description
              ? "<p>" + escapeHtml(parameter.description) + "</p>"
              : "") +
            "</div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderRequestBody(requestBody) {
    if (!requestBody || !requestBody.content) {
      return "<p class=\"swagger-empty\">요청 본문이 없습니다.</p>";
    }

    var mediaTypes = Object.keys(requestBody.content);

    return (
      "<div class=\"swagger-grid\">" +
      mediaTypes
        .map(function (mediaType) {
          var media = requestBody.content[mediaType] || {};
          return (
            "<div class=\"swagger-kv-card\">" +
            "<div class=\"swagger-kv-head\">" +
            "<strong>" + escapeHtml(mediaType) + "</strong>" +
            "<span>body</span>" +
            "</div>" +
            "<p>스키마: <code>" +
            escapeHtml(resolveSchemaName(media.schema)) +
            "</code></p>" +
            (media.example
              ? "<pre><code>" + escapeHtml(formatJson(media.example)) + "</code></pre>"
              : "") +
            "</div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderResponses(responses) {
    var entries = Object.entries(responses || {});

    if (!entries.length) {
      return "<p class=\"swagger-empty\">응답 정의가 없습니다.</p>";
    }

    return (
      "<div class=\"swagger-grid\">" +
      entries
        .map(function (entry) {
          var statusCode = entry[0];
          var response = entry[1] || {};
          var mediaTypes = Object.keys(response.content || {});
          return (
            "<div class=\"swagger-kv-card\">" +
            "<div class=\"swagger-kv-head\">" +
            "<strong>" + escapeHtml(statusCode) + "</strong>" +
            "<span>response</span>" +
            "</div>" +
            (response.description
              ? "<p>" + escapeHtml(response.description) + "</p>"
              : "") +
            (mediaTypes.length
              ? "<p>콘텐츠: <code>" + escapeHtml(mediaTypes.join(", ")) + "</code></p>"
              : "<p>콘텐츠 정의 없음</p>") +
            "</div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function renderOperation(pathKey, method, operation, tagName) {
    var summary = operation.summary || operation.operationId || pathKey;
    var operationId = operation.operationId || "";

    return (
      "<details class=\"swagger-operation\" open>" +
      "<summary>" +
      "<span class=\"swagger-method\" style=\"background:" +
      escapeHtml(getMethodColor(method)) +
      "\">" +
      escapeHtml(method) +
      "</span>" +
      "<span class=\"swagger-path\">" + escapeHtml(pathKey) + "</span>" +
      "<span class=\"swagger-summary\">" + escapeHtml(summary) + "</span>" +
      "</summary>" +
      "<div class=\"swagger-operation-body\">" +
      "<div class=\"swagger-meta-row\">" +
      "<span class=\"swagger-chip\">tag: " + escapeHtml(tagName) + "</span>" +
      (operationId
        ? "<span class=\"swagger-chip\">operationId: " + escapeHtml(operationId) + "</span>"
        : "") +
      "</div>" +
      (operation.description
        ? "<p class=\"swagger-description\">" + escapeHtml(operation.description) + "</p>"
        : "") +
      "<section>" +
      "<h4>Parameters</h4>" +
      renderParameterList(operation.parameters) +
      "</section>" +
      "<section>" +
      "<h4>Request Body</h4>" +
      renderRequestBody(operation.requestBody) +
      "</section>" +
      "<section>" +
      "<h4>Responses</h4>" +
      renderResponses(operation.responses) +
      "</section>" +
      "</div>" +
      "</details>"
    );
  }

  function buildTagIndex(spec) {
    // 태그 기준으로 path/method를 묶어서 좌측 인덱스와 본문을 함께 만듭니다.
    var grouped = {};
    var paths = spec.paths || {};

    Object.keys(paths).forEach(function (pathKey) {
      var pathItem = paths[pathKey] || {};

      Object.keys(pathItem).forEach(function (methodKey) {
        var method = methodKey.toUpperCase();
        var operation = pathItem[methodKey];

        if (!operation || typeof operation !== "object") {
          return;
        }

        var tags = asArray(operation.tags);
        var primaryTag = tags[0] || "default";

        if (!grouped[primaryTag]) {
          grouped[primaryTag] = [];
        }

        grouped[primaryTag].push({
          pathKey: pathKey,
          method: method,
          operation: operation,
        });
      });
    });

    return grouped;
  }

  function renderSidebar(grouped) {
    var tagNames = Object.keys(grouped);

    if (!tagNames.length) {
      return "<p class=\"swagger-empty\">표시할 API가 없습니다.</p>";
    }

    return (
      "<nav class=\"swagger-sidebar-nav\">" +
      tagNames
        .map(function (tagName) {
          var items = grouped[tagName] || [];
          return (
            "<section class=\"swagger-sidebar-group\">" +
            "<h3>" + escapeHtml(tagName) + "</h3>" +
            "<ul>" +
            items
              .map(function (item, index) {
                var anchorId = "op-" + escapeHtml(tagName + "-" + index)
                  .replace(/[^a-zA-Z0-9_-]/g, "-")
                  .toLowerCase();
                return (
                  "<li>" +
                  "<a href=\"#" + anchorId + "\">" +
                  "<span class=\"swagger-method-mini\" style=\"color:" +
                  escapeHtml(getMethodColor(item.method)) +
                  "\">" +
                  escapeHtml(item.method) +
                  "</span>" +
                  "<span>" + escapeHtml(item.pathKey) + "</span>" +
                  "</a>" +
                  "</li>"
                );
              })
              .join("") +
            "</ul>" +
            "</section>"
          );
        })
        .join("") +
      "</nav>"
    );
  }

  function renderMain(spec, grouped) {
    var tagNames = Object.keys(grouped);

    if (!tagNames.length) {
      return "<p class=\"swagger-empty\">OpenAPI paths 정보가 없습니다.</p>";
    }

    return tagNames
      .map(function (tagName) {
        var operations = grouped[tagName] || [];

        return (
          "<section class=\"swagger-tag-section\">" +
          "<div class=\"swagger-tag-header\">" +
          "<h2>" + escapeHtml(tagName) + "</h2>" +
          "<p>이 태그에는 " + escapeHtml(operations.length) + "개의 엔드포인트가 있습니다.</p>" +
          "</div>" +
          operations
            .map(function (item, index) {
              var anchorId = "op-" + escapeHtml(tagName + "-" + index)
                .replace(/[^a-zA-Z0-9_-]/g, "-")
                .toLowerCase();

              return (
                "<div id=\"" + anchorId + "\">" +
                renderOperation(item.pathKey, item.method, item.operation, tagName) +
                "</div>"
              );
            })
            .join("") +
          "</section>"
        );
      })
      .join("");
  }

  function attachSearch(domNode) {
    // 입력값이 포함되지 않는 operation은 숨겨서 문서 탐색을 빠르게 만듭니다.
    var searchInput = domNode.querySelector("[data-role='swagger-search']");

    if (!searchInput) {
      return;
    }

    searchInput.addEventListener("input", function () {
      var keyword = searchInput.value.trim().toLowerCase();
      var operations = domNode.querySelectorAll(".swagger-operation");

      operations.forEach(function (operationNode) {
        var text = operationNode.textContent.toLowerCase();
        operationNode.parentElement.style.display =
          !keyword || text.indexOf(keyword) >= 0 ? "" : "none";
      });
    });
  }

  function renderLoadedView(domNode, spec, config) {
    var grouped = buildTagIndex(spec);
    var apiTitle = (spec.info && spec.info.title) || document.title || "API Docs";
    var apiVersion = (spec.info && spec.info.version) || "unknown";
    var apiDescription = (spec.info && spec.info.description) || "";

    domNode.innerHTML =
      "<div class=\"swagger-shell\">" +
      "<aside class=\"swagger-sidebar\">" +
      "<div class=\"swagger-brand\">" +
      "<p class=\"swagger-eyebrow\">Offline API Docs</p>" +
      "<h1>" + escapeHtml(apiTitle) + "</h1>" +
      "<p class=\"swagger-version\">version " + escapeHtml(apiVersion) + "</p>" +
      "</div>" +
      "<label class=\"swagger-search-box\">" +
      "<span>검색</span>" +
      "<input type=\"search\" data-role=\"swagger-search\" placeholder=\"path, method, tag 검색\" />" +
      "</label>" +
      "<section class=\"swagger-side-card\">" +
      "<h2>OpenAPI URL</h2>" +
      "<code>" + escapeHtml(config.url || "") + "</code>" +
      "</section>" +
      "<section class=\"swagger-side-card\">" +
      "<h2>Servers</h2>" +
      renderServers(spec) +
      "</section>" +
      renderSidebar(grouped) +
      "</aside>" +
      "<main class=\"swagger-main\">" +
      "<section class=\"swagger-hero\">" +
      "<p class=\"swagger-eyebrow\">FastAPI / OpenAPI</p>" +
      "<h2>" + escapeHtml(apiTitle) + "</h2>" +
      (apiDescription
        ? "<p class=\"swagger-description\">" + escapeHtml(apiDescription) + "</p>"
        : "<p class=\"swagger-description\">폐쇄망에서도 열람할 수 있도록 로컬 정적 자산으로 렌더링한 API 문서입니다.</p>") +
      "</section>" +
      renderMain(spec, grouped) +
      "</main>" +
      "</div>";

    attachSearch(domNode);
  }

  function renderLoading(domNode) {
    domNode.innerHTML =
      "<div class=\"swagger-loading\">" +
      "<div class=\"swagger-spinner\"></div>" +
      "<p>OpenAPI 문서를 불러오는 중입니다...</p>" +
      "</div>";
  }

  function renderError(domNode, message) {
    domNode.innerHTML =
      "<div class=\"swagger-error\">" +
      "<h2>문서를 불러오지 못했습니다.</h2>" +
      "<p>" + escapeHtml(message) + "</p>" +
      "</div>";
  }

  function bootstrap(config) {
    var domNode = document.querySelector(config.dom_id || "#swagger-ui");

    if (!domNode) {
      return {
        initOAuth: function () {
          // 호환성 유지를 위한 no-op 함수입니다.
        },
      };
    }

    renderLoading(domNode);

    fetch(config.url, {
      headers: {
        Accept: "application/json",
      },
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("OpenAPI 응답이 비정상입니다. status=" + response.status);
        }
        return response.json();
      })
      .then(function (spec) {
        renderLoadedView(domNode, spec, config);
      })
      .catch(function (error) {
        renderError(domNode, error.message || "알 수 없는 오류가 발생했습니다.");
      });

    return {
      initOAuth: function () {
        // 폐쇄망 문서 뷰어 목적이므로 OAuth UI 초기화는 생략합니다.
      },
    };
  }

  // FastAPI가 기대하는 전역 함수 이름을 그대로 노출합니다.
  window.SwaggerUIBundle = function (config) {
    return bootstrap(config || {});
  };

  // FastAPI HTML 템플릿이 참조하는 정적 속성도 함께 제공합니다.
  window.SwaggerUIBundle.presets = {
    apis: {},
  };
  window.SwaggerUIBundle.SwaggerUIStandalonePreset = {};
})();
